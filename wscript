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


for j in (InstallContext, UninstallContext):

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
    opt.load("compiler_c compiler_cxx")
    opt.add_option(
        "--confcache",
        dest="confcache",
        default=0,
        action="count",
        help="Use a configuration cache",
    )

    gbo = opt.add_option_group("googletest build options")
    opt.option_groups["googletest options"] = gbo
    gbo.add_option(
        "--googletest-build",
        dest="googletest_build",
        default=False,
        action="store_true",
        help="Build googletest as part of the configuration step",
    )
    gbo.add_option(
        "--googletest-build-tool",
        dest="googletest_build_tool",
        type="choice",
        choices=["bazel", "cmake", "no-build"],
        default="bazel",
        action="store",
        help="Build googletest as part of the configuration step",
    )
    gbo.add_option(
        "--googletest-build-config",
        dest="googletest_build_config",
        type="choice",
        choices=["Debug", "Release"],
        default="Debug",
        action="store",
        help="Build configuration (only valid for cmake build)",
    )
    gbo.add_option(
        "--googletest-version",
        dest="googletest_version",
        default="93748a946684defd1494d5585dbc912e451e83f8",
        action="store",
        help="Commit of googletest to be built",
    )


def configure(cnf):
    if " " in cnf.path.abspath():
        cnf.fatal("Project path must not contain spaces.")
    if not Utils.is_win32:
        cnf.fatal("Operating system currently not supported.")
    if not platform.architecture()[0].startswith("64"):
        cnf.fatal("Only 64bit supported.")

    cnf.load("compiler_c compiler_cxx")

    if cnf.options.googletest_build:
        gtest_clone_dir = os.path.join(
            cnf.path.get_bld().abspath(),
            f"googletest-{cnf.options.googletest_version}",
        )
        if not os.path.exists(gtest_clone_dir):
            cnf.start_msg("Cloning repository")
            repo = git.Repo.clone_from(
                "https://github.com/google/googletest.git",
                gtest_clone_dir,
            )
        else:
            cnf.start_msg("Found Repository")
            repo = git.Repo(gtest_clone_dir)
        repo.git.checkout(cnf.options.googletest_version)
        cnf.end_msg(f"ok (on {cnf.options.googletest_version})")
        cnf.env.GOOGLETEST_BUILD_TOOL = cnf.options.googletest_build_tool.lower()
        cnf.env.GOOGLETEST_BUILD_CONFIG = cnf.options.googletest_build_config.lower()
        if cnf.options.googletest_build_tool == "bazel":
            gtest_build_dir = "bazel-bin"
            cnf.find_program("bazel")
            cnf.find_program("ninja")
            cnf.start_msg("Build googletest using bazel")
            try:
                (out, _) = cnf.cmd_and_log(
                    [cnf.env.BAZEL[0], "build", "-c", "opt", "//:gtest"],
                    output=Context.BOTH,
                    cwd=cnf.root.find_node(gtest_clone_dir).abspath(),
                )
            except Errors.WafError as err:
                if hasattr(err, "stdout"):
                    print(err.stdout)
                if hasattr(err, "stderr"):
                    cnf.fatal(err.stderr)
            if Logs.verbose:
                print(out)
            gtest_include = os.path.join(gtest_clone_dir, "googletest", "include")
            gtest_lib = os.path.join(gtest_clone_dir, gtest_build_dir)
            gtest_lib_name = "gtest"
            cnf.end_msg(True)
        elif cnf.options.googletest_build_tool == "cmake":
            cnf.env.BUILD_TOOL = "cmake"
            cnf.env.BUILD_TYPE = cnf.options.googletest_build_config.lower()
            gtest_build_dir = cnf.root.make_node(os.path.join(gtest_clone_dir, "build"))
            gtest_build_dir.mkdir()
            cnf.find_program("cmake")
            cnf.start_msg("Build googletest using cmake")
            try:
                (out, _) = cnf.cmd_and_log(
                    [
                        cnf.env.CMAKE[0],
                        "..",
                        "-DCMAKE_GENERATOR_PLATFORM=x64",
                        f"-DCMAKE_CONFIGURATION_TYPES={cnf.options.googletest_build_config}",
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
            cnf.find_program("msbuild")
            cnf.start_msg("Building googletest")
            try:
                (out, _) = cnf.cmd_and_log(
                    [
                        cnf.env.MSBUILD[0],
                        "googletest-distribution.sln",
                        "/t:Build",
                        f"/p:Configuration={cnf.options.googletest_build_config}",
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
            gtest_include = os.path.join(gtest_clone_dir, "googletest", "include")
            gtest_lib = os.path.join(
                gtest_build_dir.abspath(), "lib", cnf.options.googletest_build_config
            )
            if cnf.options.googletest_build_config.lower() == "debug":
                gtest_lib_name = "gtestd"
            elif cnf.options.googletest_build_config.lower() == "release":
                gtest_lib_name = "gtest"

        cnf.end_msg(True)
    elif cnf.options.googletest_build_tool == "no-build":
        if os.environ.get("GTEST_INC_PATH", None):
            gtest_include = os.environ.get("GTEST_INC_PATH")
        if os.environ.get("GTEST_LIB_PATH", None):
            gtest_lib = os.environ.get("GTEST_LIB_PATH")
        if os.environ.get("GTEST_LIB_NAME", None):
            gtest_lib_name = os.environ.get("GTEST_LIB_NAME")
    else:
        gtest_include = ""
        gtest_lib = ""
        gtest_lib_name = "gtest"
    cnf.env.append_unique("INCLUDES", [gtest_include])
    cnf.env.append_unique(f"LIBPATH_{gtest_lib_name.upper()}", [gtest_lib])

    try:
        header = os.path.join("gtest", "gtest.h")
        cnf.check_cxx(header_name=header)
    except Errors.ConfigurationError:
        cnf.fatal(
            f'Could not find googletest header "{header}".\n'
            'Use option "--googletest-build" to build the googletest.'
        )

    cnf.env.GTEST_LIB_NAME = gtest_lib_name.upper()
    cnf.check_cxx(lib=gtest_lib_name, use=cnf.env.GTEST_LIB_NAME)

    if cnf.env.GOOGLETEST_BUILD_TOOL == "bazel":
        cnf.env.append_unique("CFLAGS_TESTBUILD", ["/MD"])
        cnf.env.append_unique("CXXFLAGS_TESTBUILD", ["/MD"])
    elif cnf.env.GOOGLETEST_BUILD_TOOL == "cmake":
        if cnf.env.GOOGLETEST_BUILD_CONFIG == "debug":
            cnf.env.append_unique("CFLAGS_TESTBUILD", ["/MTd"])
            cnf.env.append_unique("CXXFLAGS_TESTBUILD", ["/MTd"])
        elif cnf.env.GOOGLETEST_BUILD_CONFIG == "release":
            cnf.env.append_unique("CFLAGS_TESTBUILD", ["/MT"])
            cnf.env.append_unique("CXXFLAGS_TESTBUILD", ["/MT"])


def build(bld):
    if not bld.variant:
        bld.fatal("Use 'build_bin' or 'build_test'.")
    if bld.variant == "bin":
        bld.recurse("src")
    elif bld.variant == "test":
        bld.recurse("tests")
