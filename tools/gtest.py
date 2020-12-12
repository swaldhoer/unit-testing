# SPDX-License-Identifier: MIT

from waflib import Logs
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
