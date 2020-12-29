# SPDX-License-Identifier: MIT

import os
import platform

import git

from waflib import Context, Errors, TaskGen, Utils, Logs
from waflib.Build import BuildContext, CleanContext, InstallContext, UninstallContext

Context.Context.line_just = 58

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
    opt.load("waf_unit_test")
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
        default="18f8200e3079b0e54fa00cb7ac55d4c39dcf6da6",
        action="store",
        help="Commit of googletest to be built",
    )


def configure(cnf):
    if " " in cnf.path.abspath():
        cnf.fatal("Project path must not contain spaces.")
    if not Utils.unversioned_sys_platform() in ["win32"]:
        cnf.fatal("Operating system currently not supported.")
    if not platform.architecture()[0].startswith("64"):
        cnf.fatal("Only 64bit supported.")

    cnf.load("compiler_c compiler_cxx")
    gtest_include = None
    gtest_lib_dir = None
    gtest_lib_name = "gtest"
    gmock_lib_dir = None
    gmock_lib_name = None
    gmock_include = None
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
            out = ""
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
            gtest_lib_dir = os.path.join(gtest_clone_dir, gtest_build_dir)
            gtest_lib_name = "gtest"
            gmock_include = os.path.join(gtest_clone_dir, "googlemock", "include")
            cnf.end_msg(True)
        elif cnf.options.googletest_build_tool == "cmake":
            cnf.msg("Building", str(cnf.options.googletest_build_config))
            cnf.env.BUILD_TOOL = "cmake"
            cnf.env.BUILD_TYPE = cnf.options.googletest_build_config.lower()
            gtest_build_dir = cnf.root.make_node(os.path.join(gtest_clone_dir, "build"))
            gtest_build_dir.mkdir()
            cnf.find_program("cmake")
            cnf.start_msg("Build googletest using cmake")
            cmake_args = [".."]
            if Utils.unversioned_sys_platform() == "win32":
                cmake_args.extend(
                    [
                        "-DCMAKE_GENERATOR_PLATFORM=x64",
                        f"-DCMAKE_CONFIGURATION_TYPES={cnf.options.googletest_build_config}",
                        "-DBUILD_GMOCK=ON",
                    ]
                )
            out = ""
            try:
                (out, _) = cnf.cmd_and_log(
                    cnf.env.CMAKE + cmake_args,
                    output=Context.BOTH,
                    cwd=gtest_build_dir.abspath(),
                )
            except Errors.WafError as err:
                if hasattr(err, "stdout"):
                    print(err.stdout)
                if hasattr(err, "stderr"):
                    cnf.fatal(err.stderr)
            if Logs.verbose and out:
                print(out)
            cnf.end_msg(True)
            cnf.start_msg("Building googletest")
            if Utils.unversioned_sys_platform() == "win32":
                cnf.find_program("msbuild")
                cwd = gtest_build_dir.abspath()
                cmd = cnf.env.MSBUILD + [
                    "googletest-distribution.sln",
                    "/t:Build",
                    f"/p:Configuration={cnf.options.googletest_build_config}",
                    "/p:Platform=x64",
                ]
            out = ""
            try:
                (out, _) = cnf.cmd_and_log(cmd, output=Context.BOTH, cwd=cwd)
            except Errors.WafError as err:
                if hasattr(err, "stdout"):
                    print(err.stdout)
                if hasattr(err, "stderr"):
                    cnf.fatal(err.stderr)
            if Logs.verbose and out:
                print(out)
            gtest_include = os.path.join(gtest_clone_dir, "googletest", "include")
            gtest_lib_dir = os.path.join(
                gtest_build_dir.abspath(), "lib", cnf.options.googletest_build_config
            )
            gmock_lib_dir = os.path.join(
                gtest_build_dir.abspath(), "lib", cnf.options.googletest_build_config
            )
            if cnf.options.googletest_build_config.lower() == "debug":
                gtest_lib_name = "gtestd"
                gmock_lib_name = "gmockd"
            elif cnf.options.googletest_build_config.lower() == "release":
                gtest_lib_name = "gtest"
                gmock_lib_name = "gmock"
            gmock_include = os.path.join(gtest_clone_dir, "googlemock", "include")
            cnf.end_msg(True)
    elif cnf.options.googletest_build_tool == "no-build":
        if os.environ.get("GTEST_INC_PATH", None):
            gtest_include = os.environ.get("GTEST_INC_PATH")
        if os.environ.get("GTEST_LIB_PATH", None):
            gtest_lib_dir = os.environ.get("GTEST_LIB_PATH")
        if os.environ.get("GTEST_LIB_NAME", None):
            gtest_lib_name = os.environ.get("GTEST_LIB_NAME")
        if os.environ.get("GMOCK_INC_PATH", None):
            gmock_include = os.environ.get("GMOCK_INC_PATH")
        if os.environ.get("GMOCK_LIB_PATH", None):
            gmock_include = os.environ.get("GMOCK_LIB_PATH")
        if os.environ.get("GMOCK_LIB_NAME", None):
            gmock_include = os.environ.get("GMOCK_LIB_NAME")

    if gtest_include:
        cnf.env.append_unique("INCLUDES", [gtest_include])
    if gtest_lib_dir:
        cnf.env.append_unique(f"LIBPATH_{gtest_lib_name.upper()}", [gtest_lib_dir])
    if gmock_include:
        cnf.env.append_unique("INCLUDES", [gmock_include])
    if gmock_lib_dir:
        cnf.env.append_unique(f"LIBPATH_{gmock_lib_name.upper()}", [gmock_lib_dir])

    gtest_header = os.path.join("gtest", "gtest.h")
    try:
        cnf.check_cxx(header_name=gtest_header)
    except Errors.ConfigurationError:
        cnf.fatal(
            f'Could not find googletest header "{gtest_header}".\n'
            'Use option "--googletest-build" to build the googletest.'
        )

    gmock_header = os.path.join("gmock", "gmock.h")
    cnf.check_cxx(header_name=gmock_header)

    cnf.env.GTEST_LIB_NAME = gtest_lib_name.upper()
    cnf.check_cxx(stlib=gtest_lib_name, use=cnf.env.GTEST_LIB_NAME)

    if cnf.env.GOOGLETEST_BUILD_TOOL == "cmake":
        cnf.env.GMOCK_LIB_NAME = gmock_lib_name.upper()
        cnf.check_cxx(stlib=gmock_lib_name, use=cnf.env.GMOCK_LIB_NAME)
    else:
        cnf.env.GMOCK_LIB_NAME = ""

    if not Utils.is_win32:
        cnf.check_cxx(
            features="cxx cxxprogram",
            fragment="int main() { return 0; }\n",
            ldflags="-pthread",
            msg="Checking for pthread",
        )
        cnf.env.append_unique("LDFLAGS_TESTBUILD", ["-pthread"])

    def full_test(bld):
        header = bld.srcnode.make_node("test.h")
        header.write(
            "#ifndef SUPER_H_\n#define SUPER_H_\n"
            "int add(int a, int b);\n"
            "#endif /* SUPER_H_ */\n",
            "w",
            encoding="utf-8",
        )
        sources = []
        sources.append(bld.srcnode.make_node("test.c"))
        sources[0].write(
            '#include "test.h"\nint add(int a, int b) {\nreturn a + b;\n}\n',
            "w",
            encoding="utf-8",
        )
        sources.append(bld.srcnode.make_node("testrunner.cpp"))
        sources[1].write(
            "#include <gtest/gtest.h>\n"
            "\n"
            'extern "C" {\n'
            f'#include "{header}"\n'
            "}\n"
            "\n"
            "TEST(testrunner, test_add) {\n"
            "    int a = add(1,1);\n"
            "    ASSERT_EQ(a, 3);\n"
            "}\n"
            "\n"
            "\n"
            "int main(int argc, char **argv) {\n"
            "    ::testing::InitGoogleTest(&argc, argv);\n"
            "    return RUN_ALL_TESTS();\n"
            "}\n",
            "w",
            encoding="utf-8",
        )
        cflags = []
        cxxflags = []

        if bld.env.CXX_NAME.lower() == "msvc":
            cflags = ["/EHa"] + bld.env.CFLAGS_TESTBUILD
            cxxflags = ["/EHa"] + bld.env.CXXFLAGS_TESTBUILD
        bld(
            features="c cxx cxxprogram",
            source=sources,
            use=bld.env.GTEST_LIB_NAME,
            includes=".",
            cflags=cflags,
            cxxflags=cxxflags,
            ldflags=bld.env.LDFLAGS_TESTBUILD,
            target="testrunner",
        )

    cnf.start_msg("Setting C/CXX flags for testing")
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
    cnf.end_msg(True)

    cnf.check(
        build_fun=full_test,
        execute=True,
        msg=f"Checking for static library {gtest_lib_name} and header {gtest_header}",
    )
    cnf.env.APPNAME = APPNAME


def build(bld):
    if not bld.variant:
        bld.fatal("Use 'build_bin' or 'build_test'.")
    if bld.variant == "bin":
        bld.recurse("src")
    elif bld.variant == "test":
        bld.recurse("tests")
