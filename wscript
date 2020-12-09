import os
import platform

import git

from waflib import Context, Errors, TaskGen, Utils, Logs
from waflib.Build import BuildContext, CleanContext, InstallContext, UninstallContext

for i in "bin test".split():
    for j in (BuildContext, CleanContext):

        class Tmp0(j):
            cmd = j.__name__.replace("Context", "").lower() + "_" + i
            variant = i


for j in (BuildContext, CleanContext, InstallContext, UninstallContext):

    class Tmp1(j):
        ctx = "bin"
        cmd = j.__name__.replace("Context", "").lower() + "_" + ctx
        variant = ctx


APPNAME = "Superproject"
VERSION = "0.1.0"

USE_ABSOLUTE_INCPATHS = ["\\Microsoft Visual Studio\\", "\\Windows Kits\\"]


@TaskGen.feature("c", "cxx", "includes")
@TaskGen.after_method("apply_incpaths")
def make_msvc_and_win_paths_absolute(self):
    incpaths_fixed = []
    for inc_path in self.env.INCPATHS:
        if any(i in inc_path for i in USE_ABSOLUTE_INCPATHS):
            incpaths_fixed.append(os.path.abspath(inc_path))
        else:
            incpaths_fixed.append(inc_path)
    self.env.INCPATHS = incpaths_fixed


def options(opt):
    opt.parser.remove_option("--top")
    opt.parser.remove_option("--out")
    opt.add_option(
        "--confcache",
        dest="confcache",
        default=0,
        action="count",
        help="Use a configuration cache",
    )
    opt.add_option(
        "--build-googletest",
        dest="build_googletest",
        default=False,
        action="store_true",
        help="Build googletest as part of the configuration step",
    )
    opt.add_option(
        "--googletest-version",
        dest="googletest_version",
        default="93748a946684defd1494d5585dbc912e451e83f8",
        action="store",
        help="Commit of googletest to be built",
    )
    opt.load("compiler_c compiler_cxx")


def configure(cnf):
    if " " in cnf.path.abspath():
        cnf.fatal("Project path must not contain spaces.")
    if not Utils.is_win32:
        cnf.fatal("Operating system currently not supported.")
    if not platform.architecture()[0].startswith("64"):
        cnf.fatal("Only 64bit supported.")

    cnf.load("compiler_c compiler_cxx")

    gtest_clone_dir = os.path.join(
        cnf.path.get_bld().abspath(), f"googletest-{cnf.options.googletest_version}"
    )
    gtest_build_dir = cnf.root.make_node(os.path.join(gtest_clone_dir, "build"))

    if cnf.options.build_googletest:
        cnf.start_msg("Cloning repository")
        if not os.path.exists(gtest_clone_dir):
            repo = git.Repo.clone_from(
                "https://github.com/google/googletest.git", gtest_clone_dir
            )
        else:
            repo = git.Repo(gtest_clone_dir)
        repo.git.checkout(cnf.options.googletest_version)
        cnf.end_msg(f"ok (on {cnf.options.googletest_version})")
        gtest_build_dir.mkdir()
        cnf.find_program("cmake")
        cnf.start_msg("Configure googletest cmake project")
        try:
            (out, _) = cnf.cmd_and_log(
                [cnf.env.CMAKE[0], "..", "-DCMAKE_GENERATOR_PLATFORM=x64"],
                output=Context.BOTH,
                cwd=gtest_build_dir.abspath(),
            )
        except Errors.WafError as err:
            if hasattr(err, "stdout"):
                print(err.stdout)
            if hasattr(err, "stderr"):
                cnf.fatal(err.stderr)
        if Logs.verbose:
            print(out)
        cnf.end_msg(True)
        cnf.find_program("msbuild")
        cnf.start_msg("Building googletest")
        try:
            (out, _) = cnf.cmd_and_log(
                [
                    cnf.env.MSBUILD[0],
                    "googletest-distribution.sln",
                    "/t:Build",
                    "/p:Configuration=Debug",
                    "/p:Platform=x64",
                ],
                output=Context.BOTH,
                cwd=gtest_build_dir.abspath(),
            )
        except Errors.WafError as err:
            if hasattr(err, "stdout"):
                print(err.stdout)
            if hasattr(err, "stderr"):
                cnf.fatal(err.stderr)
        if Logs.verbose:
            print(out)

        cnf.end_msg(True)

    cnf.env.append_unique(
        "INCLUDES", [os.path.join(gtest_clone_dir, "googletest", "include")]
    )
    cnf.env.append_unique(
        "LIBPATH_GTESTD", [os.path.join(gtest_build_dir.abspath(), "lib", "Debug")]
    )

    try:
        header = os.path.join("gtest", "gtest.h")
        cnf.check_cxx(header_name=header)
    except Errors.ConfigurationError:
        cnf.fatal(
            f'Could not find googletest header "{header}".\n'
            'Use option "--build-googletest" to build the googletest.'
        )
    cnf.check_cxx(lib="gtestd", use="GTESTD")


def build(bld):
    if not bld.variant:
        bld.fatal("Use 'build_bin' or 'build_test'.")
    if bld.variant == "bin":
        bld.recurse("src")
    elif bld.variant == "test":
        bld.recurse("tests")
