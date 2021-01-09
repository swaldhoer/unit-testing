# SPDX-License-Identifier: MIT

from waflib import Logs, Utils
from waflib.Tools import waf_unit_test

ERROR_WORDS = ["error:", "FAILED"]


def summary(bld):
    lst = getattr(bld, "utest_results", [])
    if not lst:
        return
    for i in lst:
        err_mode = False
        for line in i[2].decode().splitlines():
            if any(i in line for i in ERROR_WORDS) or err_mode:
                Logs.error(f"    {line}")
                err_mode = True
                if "FAILED" in line:
                    err_mode = False
            else:
                Logs.info(f"    {line}")
    waf_unit_test.summary(bld)


def configure(cnf):
    if Utils.unversioned_sys_platform() == "win32":
        cnf.find_program("python", var="PYTHON")
    elif Utils.unversioned_sys_platform() == "linux":
        cnf.find_program("gcov", var="GCOV")
        cnf.find_program("gcovr", var="GCOVR")
        cnf.find_program("python3", var="PYTHON")
