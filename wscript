# SPDX-License-Identifier: MIT

import os
import platform
import shutil

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


class GDeps:  # pylint: disable=too-many-instance-attributes
    def __init__(self, source="", build_tool="unknown", build_config="Release"):
        self.source = source
        self.build_tool = build_tool
        if self.build_tool in ("unknown", "bazel"):
            self.build_config = "Release"
        elif self.build_tool == "cmake":
            self.build_config = str(build_config)
        self.gtest_include = ""
        self.gtest_lib_dir = ""
        self.gtest_lib_name = ""
        self.gmock_lib_dir = ""
        self.gmock_lib_name = ""
        self.gmock_include = ""

        self.gtest_header = os.path.join("gtest", "gtest.h")
        self.gmock_header = os.path.join("gmock", "gmock.h")

    def __str__(self):
        return (
            f"info:  {self.source}, {self.build_tool}, {self.build_config}>\n"
            f"gtest: {self.gtest_include}, {self.gtest_lib_dir}, {self.gtest_lib_name}\n"
            f"gmock: {self.gmock_include}, {self.gmock_lib_dir}, {self.gmock_lib_name}"
        )


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
    opt.load("clang_format")
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

    gbo = opt.add_option_group("googletest bootstrap options")
    opt.option_groups["googletest bootstrap options"] = gbo
    gbo.add_option(
        "--googletest-bootstrap",
        dest="googletest_bootstrap",
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
    bootstrap_dir = os.path.join(os.path.expanduser("~"), "googletest")
    gbo.add_option(
        "--googletest-bootstrap-directory",
        dest="googletest_bootstrap_directory",
        default=bootstrap_dir,
        action="store",
        help="Directory for bootstrapping googletest",
    )


def configure(cnf):
    def cmd_and_log_error(err):
        if hasattr(err, "stdout"):
            print(err.stdout)
        if hasattr(err, "stderr"):
            cnf.fatal(err.stderr)

    def bootstrap():
        # get the latest version of the googletest repository and make a copy
        # that contains the specific commit of googletest that should be build
        os.makedirs(cnf.options.googletest_bootstrap_directory, exist_ok=True)
        gtest_clone_dir = os.path.join(
            cnf.options.googletest_bootstrap_directory, "googletest"
        )
        if not os.path.exists(gtest_clone_dir):
            cnf.start_msg("Cloning googletest repository")
            repo = git.Repo.clone_from(
                "https://github.com/google/googletest.git",
                gtest_clone_dir,
            )
        else:
            cnf.start_msg("Found Repository")
            repo = git.Repo(gtest_clone_dir)
        cnf.end_msg(gtest_clone_dir)
        cnf.start_msg("Cleaning repository")
        repo.git.clean("-xdf")
        cnf.end_msg(True)
        default_branch_cmd = repo.git.ls_remote(
            "--symref", "--symref", "origin", "HEAD"
        )
        default_branch_name = "master"
        for line in default_branch_cmd.splitlines():
            if not line.lower().startswith("ref:"):
                continue
            info = line.split()
            try:
                default_branch_name = info[1]
            except IndexError:
                Logs.warn(
                    "Could not determine default branch name, using"
                    f"'{default_branch_name}'."
                )
        default_branch_name = default_branch_name.split("/")[-1]
        repo.git.checkout(default_branch_name)
        repo.git.pull()
        cnf.start_msg("Checking out commit")
        repo.git.checkout(cnf.options.googletest_version)
        cnf.end_msg(cnf.options.googletest_version)
        gtest_version_dir = gtest_clone_dir + "-" + cnf.options.googletest_version
        if not os.path.isdir(gtest_version_dir):
            shutil.copytree(gtest_clone_dir, gtest_version_dir)

        repo.git.checkout(default_branch_name)

        # build googletest and googlemock library with the specified tool
        d = GDeps(
            gtest_version_dir,
            cnf.options.googletest_build_tool,
            cnf.options.googletest_build_config,
        )

        # start actual build
        if d.build_tool == "bazel":
            gtest_build_dir = "bazel-bin"
            cnf.find_program("bazel")
            cnf.find_program("ninja")
            cnf.start_msg("Build googletest using bazel")
            out = ""
            cmd = cnf.env.BAZEL + ["build", "-c", "opt", "//:gtest"]
            cwd = cnf.root.find_node(d.source).abspath()
            try:
                (out, _) = cnf.cmd_and_log(cmd, output=Context.BOTH, cwd=cwd)
            except Errors.WafError as err:
                cmd_and_log_error(err)
            if Logs.verbose:
                print(out)
            d.gtest_include = os.path.join(d.source, "googletest", "include")
            d.gtest_lib_dir = os.path.join(d.source, gtest_build_dir)
            d.gtest_lib_name = "gtest"
            d.gmock_include = os.path.join(d.source, "googlemock", "include")
            cnf.end_msg(True)
        elif d.build_tool == "cmake":
            gtest_build_dir = cnf.root.make_node(os.path.join(d.source, "build"))
            gtest_build_dir.mkdir()
            gtest_build_dir_abs = gtest_build_dir.abspath()
            cnf.find_program("cmake")
            cnf.start_msg("Build googletest using cmake")
            cmake_args = [".."]
            if Utils.unversioned_sys_platform() == "win32":
                if cnf.env.CXX_NAME == "msvc":
                    cmake_args.extend(
                        [
                            "-DCMAKE_GENERATOR_PLATFORM=x64",
                            f"-DCMAKE_CONFIGURATION_TYPES={d.build_config}",
                            "-DBUILD_GMOCK=ON",
                        ]
                    )
                elif cnf.env.CXX_NAME == "gcc":
                    cmake_args.extend(
                        [
                            "-GMinGW Makefiles",
                            # "-Dgtest_build_samples=ON",
                            # "-Dgtest_build_tests=ON",
                            # "-Dgmock_build_tests=ON",
                            "-Dcxx_no_exception=OFF",
                            "-Dcxx_no_rtti=OFF",
                            "-DCMAKE_COMPILER_IS_GNUCXX=OFF",
                            "-DCMAKE_CXX_FLAGS=-std=c++11 -Wdeprecated",
                            f"-DCMAKE_BUILD_TYPE={d.build_config}",
                            "-DBUILD_GMOCK=ON",
                            "-DCMAKE_CXX_FLAGS=-Wa,-mbig-obj",
                        ]
                    )
            elif Utils.unversioned_sys_platform() == "linux":
                cmake_args.extend(
                    [
                        "-GUnix Makefiles",
                        "-Dgtest_build_samples=ON",
                        "-Dgtest_build_tests=ON",
                        "-Dgmock_build_tests=ON",
                        "-Dcxx_no_exception=OFF",
                        "-Dcxx_no_rtti=OFF",
                        "-DCMAKE_COMPILER_IS_GNUCXX=OFF",
                        "-DCMAKE_CXX_FLAGS=-std=c++11 -Wdeprecated",
                        f"-DCMAKE_BUILD_TYPE={d.build_config}",
                        "-DBUILD_GMOCK=ON",
                    ]
                )
            out = ""
            cmd = cnf.env.CMAKE + cmake_args
            cwd = gtest_build_dir_abs
            try:
                (out, _) = cnf.cmd_and_log(cmd, output=Context.BOTH, cwd=cwd)
            except Errors.WafError as err:
                cmd_and_log_error(err)
            if Logs.verbose and out:
                print(out)
            cnf.end_msg(True)

            cnf.start_msg("Building googletest")
            if Utils.unversioned_sys_platform() == "win32":
                if cnf.env.CXX_NAME == "msvc":
                    cnf.find_program("msbuild")
                    cwd = gtest_build_dir_abs
                    cmd = cnf.env.MSBUILD + [
                        "googletest-distribution.sln",
                        "/t:Build",
                        f"/p:Configuration={d.build_config}",
                        "/p:Platform=x64",
                    ]
                elif cnf.env.CXX_NAME == "gcc":
                    cnf.find_program("make", mandatory=False)
                    if not cnf.env.MAKE:
                        cnf.find_program("mingw32-make", var="MAKE", mandatory=True)
                    cwd = gtest_build_dir_abs
                    cmd = cnf.env.MAKE
            elif Utils.unversioned_sys_platform() == "linux":
                cnf.find_program("make")
                cwd = gtest_build_dir_abs
                cmd = cnf.env.MAKE

            out = ""
            try:
                (out, _) = cnf.cmd_and_log(cmd, output=Context.BOTH, cwd=cwd)
            except Errors.WafError as err:
                cmd_and_log_error(err)
            if Logs.verbose and out:
                print(out)
            d.gtest_include = os.path.join(d.source, "googletest", "include")
            if cnf.options.googletest_build_config.lower() == "debug":
                d.gtest_lib_name = "gtestd"
                d.gmock_lib_name = "gmockd"
            elif cnf.options.googletest_build_config.lower() == "release":
                d.gtest_lib_name = "gtest"
                d.gmock_lib_name = "gmock"
            d.gmock_include = os.path.join(d.source, "googlemock", "include")
            if Utils.unversioned_sys_platform() == "win32":
                if cnf.env.CXX_NAME == "msvc":
                    d.gtest_include = os.path.join(d.source, "googletest", "include")
                    d.gtest_lib_dir = os.path.join(
                        gtest_build_dir_abs,
                        "lib",
                        d.build_config,
                    )
                    d.gmock_lib_dir = os.path.join(
                        gtest_build_dir_abs, "lib", d.build_config
                    )
                elif cnf.env.CXX_NAME == "gcc":
                    d.gtest_include = os.path.join(d.source, "googletest", "include")
                    d.gtest_lib_dir = os.path.join(gtest_build_dir_abs, "lib")
                    d.gmock_lib_dir = os.path.join(gtest_build_dir_abs, "lib")

            elif Utils.unversioned_sys_platform() == "linux":
                d.gtest_include = os.path.join(d.source, "googletest", "include")
                d.gtest_lib_dir = os.path.join(gtest_build_dir_abs, "lib")
                d.gmock_lib_dir = os.path.join(gtest_build_dir_abs, "lib")
                if cnf.options.googletest_build_config.lower() == "debug":
                    d.gtest_lib_name = "gtestd"
                    d.gmock_lib_name = "gmockd"
                elif cnf.options.googletest_build_config.lower() == "release":
                    d.gtest_lib_name = "gtest"
                    d.gmock_lib_name = "gmock"
            cnf.end_msg(True)
        return d

    if " " in cnf.path.abspath():
        cnf.fatal("Project path must not contain spaces.")
    if not Utils.unversioned_sys_platform() in ["win32", "linux"]:
        cnf.fatal("Operating system currently not supported.")
    if not platform.architecture()[0].startswith("64"):
        cnf.fatal("Only 64bit supported.")

    cnf.load("compiler_c compiler_cxx")
    cnf.load("gtest")
    cnf.load("clang_format")

    if cnf.options.googletest_bootstrap:
        dep = bootstrap()
        cnf.env.GOOGLETEST_BUILD_TOOL = dep.build_tool.lower()
        cnf.env.GOOGLETEST_BUILD_CONFIG = dep.build_config.lower()
    else:
        dep = GDeps()
        dep.gtest_include = os.environ.get("GTEST_INC_PATH", "")
        dep.gtest_lib_dir = os.environ.get("GTEST_LIB_PATH", "")
        dep.gtest_lib_name = os.environ.get("GTEST_LIB_NAME", "")
        dep.gmock_include = os.environ.get("GMOCK_INC_PATH", "")
        dep.gmock_lib_dir = os.environ.get("GMOCK_LIB_PATH", "")
        dep.gmock_lib_name = os.environ.get("GMOCK_LIB_NAME", "")
    Logs.info(dep)
    if dep.gtest_include:
        cnf.env.append_unique("INCLUDES", [dep.gtest_include])
    if dep.gtest_lib_dir:
        cnf.env.append_unique(
            f"LIBPATH_{dep.gtest_lib_name.upper()}", [dep.gtest_lib_dir]
        )
    if dep.gmock_include:
        cnf.env.append_unique("INCLUDES", [dep.gmock_include])
    if dep.gmock_lib_dir:
        cnf.env.append_unique(
            f"LIBPATH_{dep.gmock_lib_name.upper()}", [dep.gmock_lib_dir]
        )

    try:
        cnf.check_cxx(header_name=dep.gtest_header)
    except Errors.ConfigurationError:
        cnf.fatal(
            f'Could not find googletest header "{dep.gtest_header}".\n'
            'Use option "--googletest-bootstrap" to build googletest.'
        )

    cnf.check_cxx(header_name=dep.gmock_header)

    cnf.env.GTEST_LIB_NAME = dep.gtest_lib_name.upper()
    cnf.check_cxx(stlib=dep.gtest_lib_name, use=cnf.env.GTEST_LIB_NAME)

    if cnf.env.GOOGLETEST_BUILD_TOOL == "cmake":
        cnf.env.GMOCK_LIB_NAME = dep.gmock_lib_name.upper()
        cnf.check_cxx(stlib=dep.gmock_lib_name, use=cnf.env.GMOCK_LIB_NAME)
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
        if Utils.unversioned_sys_platform() == "win32":
            if cnf.env.CXX_NAME.lower() == "msvc":
                cnf.env.append_unique("CFLAGS_TESTBUILD", ["/MD"])
                cnf.env.append_unique("CXXFLAGS_TESTBUILD", ["/MD"])
        elif Utils.unversioned_sys_platform() == "linux":
            pass
    elif cnf.env.GOOGLETEST_BUILD_TOOL == "cmake":
        if cnf.env.GOOGLETEST_BUILD_CONFIG == "debug":
            if Utils.unversioned_sys_platform() == "win32":
                if cnf.env.CXX_NAME.lower() == "msvc":
                    cnf.env.append_unique("CFLAGS_TESTBUILD", ["/MTd"])
                    cnf.env.append_unique("CXXFLAGS_TESTBUILD", ["/MTd"])
            elif Utils.unversioned_sys_platform() == "linux":
                pass
        elif cnf.env.GOOGLETEST_BUILD_CONFIG == "release":
            if Utils.unversioned_sys_platform() == "win32":
                if cnf.env.CXX_NAME.lower() == "msvc":
                    cnf.env.append_unique("CFLAGS_TESTBUILD", ["/MT"])
                    cnf.env.append_unique("CXXFLAGS_TESTBUILD", ["/MT"])
            elif Utils.unversioned_sys_platform() == "linux":
                pass
    cnf.end_msg(True)

    cnf.check(
        build_fun=full_test,
        execute=True,
        msg=(
            f"Checking for static library {dep.gtest_lib_name} and "
            f"header {dep.gtest_header}"
        ),
    )
    cnf.env.APPNAME = APPNAME


def build(bld):
    if not bld.variant:
        bld.fatal("Use 'build_bin' or 'build_test'.")
    if bld.variant == "bin":
        bld.recurse("src")
    elif bld.variant == "test":
        bld.recurse("tests")


def clang_format(ctx):
    excl = f"{ctx.bldnode.path_from(ctx.path)}/**"
    ctx(
        features="clang-format",
        files=ctx.path.ant_glob("**/*.c", excl=excl, quite=True, remove=False),
    )


class FormatContext(BuildContext):
    cmd = "clang-format"
    fun = "clang_format"
