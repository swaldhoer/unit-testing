# SPDX-License-Identifier: MIT

import os
import re
import hashlib


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
        if cnf.env.CXX_NAME.lower() == "msvc":
            pass
        elif cnf.env.CXX_NAME.lower() == "gcc":
            cnf.find_program("gcov", var="GCOV")
            cnf.find_program("gcovr", var="GCOVR")
    elif Utils.unversioned_sys_platform() == "linux":
        cnf.find_program("python3", var="PYTHON")
        cnf.find_program("gcov", var="GCOV")
        cnf.find_program("gcovr", var="GCOVR")
    if cnf.env.GCOVR:
        out, _ = cnf.cmd_and_log(
            [Utils.subst_vars("${GCOVR}", cnf.env), "--version"],
            quiet=Context.BOTH,
            output=Context.BOTH,
        )
        try:
            out = out.decode("utf-8")
        except AttributeError:
            pass
        version = out.split()[1].split(".")
        cnf.env.GCOVR_VERSION = tuple(version)


@feature("gcov_gcovr")
def run_gcov(self):
    if not Utils.is_win32 or self.env.CXX_NAME == "gcc":
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
        self.gcov_task = self.create_task("Gcov", src=inputs, tgt=tgt)

        excl = []
        if hasattr(self, "gcovr_excl"):
            excl.extend(Utils.to_list(self.gcovr_excl))

        gcovr_out_base = "index"
        gcovr_tgt = [
            self.path.find_or_declare(
                os.path.join(self.bld.bldnode.abspath(), gcovr_out_base + ".html")
            )
        ]
        ver = tuple(int(i) for i in self.env.GCOVR_VERSION)
        for i in self.gcov_task.outputs:
            found = False
            for j in excl:
                if re.search(j, i.abspath().replace("#", os.sep)):
                    found = True
            if found:
                continue
            if ver >= (5, 0):
                tgt_for_hash = (
                    i.name.replace("^#", "").replace("#", "/").rsplit(".gcov")[0]
                )
                hfile_name_hash = hashlib.md5(tgt_for_hash.encode("utf-8")).hexdigest()
                gcovr_out_suffix = f".{hfile_name_hash}.html"
                tgt = i.name.replace("^#", "")
                tgt_file_name = tgt.rsplit("#")[-1].replace(".gcov", gcovr_out_suffix)
                tgt = gcovr_out_base + "." + tgt_file_name
            else:
                tgt = i.name.replace("^#", "")
                tgt = (
                    gcovr_out_base
                    + "."
                    + tgt.replace("#", "_").replace(".gcov", ".html")
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
                if "removing" in line.lower():
                    continue
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
