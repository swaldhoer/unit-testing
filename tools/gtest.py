# SPDX-License-Identifier: MIT

import os
import re


from waflib.TaskGen import feature
from waflib import Context, Errors, Logs, Task, Utils
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


@feature("gcov_gcovr")
def run_gcov(self):
    if not Utils.is_win32:
        inputs = []
        for tg_name in self.input_tasks:
            tg = self.bld.get_tgen_by_name(tg_name)
            tg.post()
            inputs.extend(tg.link_task.inputs)
        tgt = []
        bld_depth = self.bld.path.get_bld().path_from(self.bld.path)
        pref_len = 1
        if bld_depth != ".":
            pref_len += bld_depth.count(os.sep)
        for i in inputs:
            pref = "^#" * pref_len
            tgt_file = pref + i.parent.relpath().replace(os.sep, "#") + "#"
            tgt_file += ".".join(i.name.split(".")[:-2]) + ".gcov"
            tgt.append(
                self.path.find_or_declare(
                    os.path.join(self.bld.path.get_bld().abspath(), tgt_file)
                )
            )
        gcovr_out_base = "index"
        gcovr_out_suffix = ".html"
        gcovr_tgt = [
            self.path.find_or_declare(
                os.path.join(
                    self.bld.bldnode.abspath(), gcovr_out_base + gcovr_out_suffix
                )
            )
        ]
        self.gcov_task = self.create_task("Gcov", src=inputs, tgt=tgt)

        excl = []
        if hasattr(self, "gcovr_excl"):
            tmp = Utils.to_list(self.gcovr_excl)
            for i in tmp:
                excl.append(i.replace(".*/", "").replace("/.*", "_"))

        for i in self.gcov_task.outputs:
            tgt = i.name.replace("^#", "")
            tgt = (
                gcovr_out_base
                + "."
                + tgt.replace("#", "_").replace(".gcov", gcovr_out_suffix)
            )
            tgt = os.path.join(self.bld.bldnode.abspath(), tgt)

            if not any(i in tgt for i in excl):
                gcovr_tgt.append(self.path.find_or_declare(tgt))
        self.create_task("Gcovr", src=self.gcov_task.outputs, tgt=gcovr_tgt)


class Gcovr(Task.Task):
    color = "PINK"
    after = ["Gcov"]

    def run(self):
        excl = []
        if hasattr(self.generator, "gcovr_excl"):
            excl = Utils.to_list(self.generator.gcovr_excl)
            excl = [f"--exclude={i}" for i in excl]
        cmd = (
            self.env.PYTHON
            + [
                "-m",
                "gcovr",
                "--use-gcov-files",
                "--html-details",
                "--keep",
            ]
            + excl
            + [
                "--output",
                self.outputs[0].abspath(),
                "--root",
                self.generator.bld.path.abspath(),
                self.generator.bld.bldnode.abspath(),
            ]
        )
        try:
            self.generator.bld.cmd_and_log(
                cmd,
                cwd=self.generator.bld.bldnode.abspath(),
                quiet=Context.BOTH,
                output=Context.BOTH,
            )
        except Errors.WafError as err:
            if hasattr(err, "stdout"):
                print(err.stdout)
            if hasattr(err, "stderr"):
                Logs.error(err.stderr)
            self.generator.bld.fatal("Could not generate coverage report.")


class Gcov(Task.Task):
    color = "PINK"
    after = ["utest"]

    def run(self):
        for i in self.inputs:
            cmd = self.env.GCOV + ["-p", i.abspath()]
            try:
                out, _ = self.generator.bld.cmd_and_log(
                    cmd,
                    cwd=self.generator.bld.bldnode.abspath(),
                    quiet=Context.BOTH,
                    output=Context.BOTH,
                )
            except Errors.WafError as err:
                if hasattr(err, "stdout"):
                    print(err.stdout)
                if hasattr(err, "stderr"):
                    Logs.error(err.stderr)

            # find files produced by gcov
            for line in out.splitlines():
                if ".gcov" in line:
                    match = re.search(r"'(.*.gcov)'", line)
                    if match.group(1):
                        gcov_file = match.group(1)
                        f_node = self.generator.bld.path.get_bld().find_node(gcov_file)
                        f_txt = f_node.read()
                        source = re.search(r"^.*Source:(.*)$", f_txt.splitlines()[0])
                        if source:
                            if not os.path.isabs(source.group(1)):
                                source_abs = os.path.abspath(
                                    os.path.join(
                                        self.generator.bld.path.get_bld().abspath(),
                                        source.group(1),
                                    )
                                )
                                f_txt = f_txt.replace(source.group(1), source_abs)
                                f_node.write(f_txt)
