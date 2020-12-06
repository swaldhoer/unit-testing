import os
import json
from waflib.Build import BuildContext, CleanContext, InstallContext, UninstallContext

for i in "bin test".split():
    for j in (BuildContext, CleanContext):
        name = j.__name__.replace("Context", "").lower()

        class tmp(j):
            cmd = name + "_" + i
            variant = i


ctx = "bin"
for i in (BuildContext, CleanContext, InstallContext, UninstallContext):
    name = i.__name__.replace("Context", "").lower()

    class tmp(i):
        cmd = name + "_" + ctx
        variant = ctx


APPNAME = "Superproject"
VERSION = "0.1.0"


def options(opt):
    opt.load("compiler_c compiler_cxx")


def configure(cnf):
    config = cnf.path.find_node(os.path.join("tests", "gtest.json"))
    if not config:
        cnf.fatal("Could not find gtest configuration")
    gtest_config = json.loads(config.read())
    cnf.load("compiler_c compiler_cxx")

    if gtest_config.get("include", None):
        cnf.env.append_unique("INCLUDES", [gtest_config.get("include")])
    if gtest_config.get("lib", None):
        cnf.env.append_unique("LIBPATH_GTESTD", [gtest_config.get("lib")])
    print(cnf.env.INCLUDES)
    print(cnf.env.LIBPATH_GTESTD)

    cnf.check_cxx(header_name="gtest/gtest.h")
    cnf.check_cxx(lib="gtestd", use="GTESTD")


def build(bld):
    if not bld.variant:
        bld.fatal("Use 'build_bin' or 'build_test'.")
    if bld.variant == "bin":
        bld.recurse("src")
    elif bld.variant == "test":
        bld.recurse("tests")
