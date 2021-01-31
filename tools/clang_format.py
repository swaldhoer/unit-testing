# SPDX-License-Identifier: MIT


from waflib import Task, TaskGen, Utils


class ClangFormat(Task.Task):
    color = "PINK"
    vars = ["CLANG_FORMAT", "CLANG_FORMAT_OPTIONS"]
    run_str = "${CLANG_FORMAT} ${CLANG_FORMAT_OPTIONS} ${SRC}"


def options(opt):
    opt.add_option(
        "--cf-arg",
        dest="cf_arg",
        action="append",
        help="Invoke clang-format with specified arguments",
    )


@TaskGen.feature("clang-format")
def create_clang_format_tasks(self):
    files = Utils.to_list(getattr(self, "files", []))
    self.env.append_unique("CLANG_FORMAT_OPTIONS", self.bld.options.cf_arg or [])
    for i in files:
        self.create_task("ClangFormat", i)


def configure(cnf):
    cnf.find_program("clang-format", var="CLANG_FORMAT")
