# SPDX-License-Identifier: LGPL-3.0-only

"""Functions to publish LaTeX documents."""

import os
import re
from typing import List

from doorstop import common, settings
from doorstop.cli import utilities
from doorstop.common import DoorstopError
from doorstop.core.publishers._latex_functions import (
    _add_comment,
    _check_for_new_table,
    _fix_table_line,
    _latex_convert,
    _typeset_latex_image,
)
from doorstop.core.publishers.base import (
    BasePublisher,
    extract_prefix,
    get_document_attributes,
    format_level,
)
from doorstop.core.template import check_latex_template_data, read_template_data
from doorstop.core.types import is_item, iter_documents, iter_items

log = common.logger(__name__)


class LaTeXPublisher(BasePublisher):
    """LaTeX publisher."""

    def __init__(self, obj, ext):
        super().__init__(obj, ext)
        self.END_LONGTABLE = "\\end{longtable}"
        self.HLINE = "\\hline"
        self.END_TABULAR = "\\end{tabular}"
        self.compile_files = []
        self.compile_path = ""
        # Define lists.
        self.list["start"] = {
            "itemize": r"\begin{itemizeDeep}",
            "enumerate": r"\begin{enumerateDeep}",
        }
        self.list["end"] = {
            "itemize": r"\end{itemizeDeep}",
            "enumerate": r"\end{enumerateDeep}",
        }
        self.list["start_item"] = {"itemize": r"\\item ", "enumerate": r"\\item "}
        self.list["end_item"] = {"itemize": "", "enumerate": ""}

    def preparePublish(self):
        """Publish wrapper files for LaTeX."""
        log.debug("Generating compile script for LaTeX from %s", self.path)
        self.compile_path = self._get_compile_path()

    def publishAction(self, document, path):
        """Add file to compile.sh script."""
        self.document = document
        # If path does not end with .tex, add it.
        if not path.endswith(".tex"):
            self.documentPath = os.path.join(path, document.prefix + ".tex")
        else:
            self.documentPath = path

        log.debug("Generating compile script for LaTeX from %s", self.documentPath)
        file_to_compile = self._generate_latex_wrapper()
        self.compile_files.append(file_to_compile)

    def concludePublish(self):
        """Write out the compile.sh file."""
        common.write_lines(
            self.compile_files,
            self.compile_path,
            end=settings.WRITE_LINESEPERATOR,
            executable=True,
        )
        msg = "You can now execute the file 'compile.sh' twice in the exported folder to produce the PDFs!"
        utilities.show(msg, flush=True)

    def create_index(self, directory, index=None, extensions=(".tex",), tree=None):
        """No index for LaTeX."""

    def table_of_contents(self, linkify=None, obj=None):
        """No table of contents LaTeX."""

    def lines(self, obj, **kwargs):
        """Yield lines for a LaTeX report.

        :param obj: Item, list of Items, or Document to publish
        :param linkify: turn links into hyperlinks

        :return: iterator of lines of text

        """
        linkify = kwargs.get("linkify", False)
        item_count = 0
        prev_level = ""
        sub_category = ""
        prev_category = ""
        prev_subcategory = ""

        for item in iter_items(obj):

            level_header = "\\" + "subsubsection{"
            heading = "\\" + "subsubsection{"
            heading_level = "\\" + "subsubsection{"

            level = format_level(item.level)
            prefix = item.document.prefix
            uid = str(item.uid)
            split_uid = uid.split("-")

            # 'Level' Header for each document w/separator
            if item_count == 0:
                if prefix.startswith("L0"):
                    yield "\\" + "section{Level- 0}"
                else:
                    yield "\\" + "section{Level- " + level + "}"
            else:
                yield "\\vspace{0.8cm}"

            # Creating subsections for each document based on adjusted levels
            if len(split_uid) == 4:
                found_prefix = str(split_uid[0])
                category = str(split_uid[1])
                sub_category = str(split_uid[2])
                if category != prev_category:
                    prev_category = category
                    prev_subcategory = sub_category
                    yield "\\subsection{" + category + "- " + sub_category + "}"
                if sub_category != prev_subcategory:
                    prev_subcategory = sub_category
                    yield "\\subsection{" + category + "- " + sub_category + "}"

            if item.heading:
                text_lines = item.text.splitlines()
                if item.header:
                    text_lines.insert(0, item.header)
                # Level and Text
                if settings.PUBLISH_HEADING_LEVELS:
                    standard = "{h}{t}{he}".format(
                        h=heading_level,
                        t=_latex_convert(text_lines[0]) if text_lines else "",
                        he="}",
                    )
                else:
                    standard = "{h}{t}{he}".format(
                        h=heading,
                        t=_latex_convert(text_lines[0]) if text_lines else "",
                        he="}",
                    )
                attr_list = self.format_attr_list(item, True)
                yield standard + attr_list
                yield from self._format_latex_text(text_lines[1:])
            else:
                uid = item.uid
                if settings.ENABLE_HEADERS:
                    if item.header:
                        uid = "{h}{{ - {u}}}".format(
                            h=_latex_convert(item.header), u=item.uid
                        )
                    else:
                        short_name = "\\small\\textit{{{s}}}".format(s=_latex_convert(item.short_name))
                        uid = "{{{u}- }}{s}".format(u=item.uid, s=short_name)

                # Level and UID
                if settings.PUBLISH_BODY_LEVELS:
                    standard = "{h}{u}{he}".format(h=heading_level, u=uid, he="}")
                else:
                    standard = "{h}{u}{he}".format(h=heading, u=uid, he="}")

                attr_list = self.format_attr_list(item, True)
                yield standard + attr_list

                # # Short Name
                # if item.short_name:
                #     yield ""  # break before text
                #     text_fixed = self._format_latex_text(item.short_name.splitlines())
                #     yield from self._format_href_text(text_fixed)
                #     yield ""

                # Text
                if item.text:
                    yield ""  # break before text
                    text_fixed = self._format_latex_text(item.text.splitlines())
                    yield from self._format_href_text(text_fixed)
                    yield ""

                # Add custom publish attributes
                if item.document and item.document.publish:
                    header_printed = False
                    for attr in item.document.publish:
                        if not item.attribute(attr):
                            continue
                        else:
                            attr_label = "\\textbf{" + attr.capitalize() + ": }"
                            attr_text = item.attribute(attr)
                            fixed_attr = self._format_latex_text(attr_text.splitlines())
                            yield attr_label
                            yield from self._format_href_text(fixed_attr)
                            yield ""

                # Reference
                if item.ref:
                    #yield ""  # break before reference
                    yield self.format_ref(item)

                # Reference
                if item.references:
                    #yield ""  # break before reference
                    yield self.format_references(item)

            # Parent Links
            if item.links:
                items1 = item.parent_items
                if items1 and settings.PUBLISH_PARENT_LINKS:
                    label = "Parent Links:"
                    links = self.format_links(items1, linkify)
                    label_links = self.format_label_links(label, links, linkify)
                    yield label_links + "\n"
                    
            # Child Links
            if settings.PUBLISH_CHILD_LINKS:
                items2 = item.find_child_items()
                if items2:
                    label = "Child Links:"
                    links = self.format_links(items2, linkify)
                    label_links = self.format_label_links(label, links, linkify)
                    yield label_links + "\n"
                    
                # Original version
                # if item.document and item.document.publish:
                #     header_printed = False
                #     for attr in item.document.publish:
                #         if not item.attribute(attr):
                #             continue
                #         if not header_printed:
                #             header_printed = True
                #             yield "\\begin{longtable}{|l|l|}"
                #             yield "\\setlength{\\LTleft}{0pt}"
                #             yield "\\begin{tabular}{p{0.2\\linewidth} | p{0.70\\linewidth}}"
                #             yield "Attribute & Values\\\\"
                #             yield self.HLINE
                #         yield "{} & {} \\\\".format(attr, item.attribute(attr))
                #     if header_printed:
                #         yield self.END_TABULAR
                #         yield self.END_LONGTABLE
                #     else:
                #         yield ""

            item_count = item_count + 1

            yield ""  # break between items
        yield ""  # break between requirements

    def format_attr_list(self, item, linkify):
        """Create a LaTeX attribute list for a heading."""
        return (
            "{l}{u}{le}{zl}{u}{le}".format(
                l="\\label{", zl="\\zlabel{", u=item.uid, le="}"
            )
            if linkify
            else ""
        )

    def format_ref(self, item):
        """Format an external reference in LaTeX."""
        if settings.CHECK_REF:
            path, line = item.find_ref()
            path = path.replace("\\", "/")  # always use unix-style paths
            if line:
                return (
                    "\\begin{{quote}} \\verb|{p}| (line {line})\\end{{quote}}".format(
                        p=path, line=line
                    )
                )
            else:
                return "\\begin{{quote}} \\verb|{p}|\\end{{quote}}".format(p=path)
        else:
            return "\\begin{{quote}} \\verb|{r}|\\end{{quote}}".format(r=item.ref)

    def format_references(self, item):
        """Format an external reference in LaTeX."""
        if settings.CHECK_REF:
            references = item.find_references()
            text_refs = []
            for ref_item in references:
                path, line = ref_item
                path = path.replace("\\", "/")  # always use unix-style paths

                if line:
                    text_refs.append(
                        "\\begin{{quote}} \\verb|{p}| (line {line})\\end{{quote}}".format(
                            p=path, line=line
                        )
                    )
                else:
                    text_refs.append(
                        "\\begin{{quote}} \\verb|{p}|\\end{{quote}}".format(p=path)
                    )

            return "\n".join(ref for ref in text_refs)
        else:
            references = item.references
            text_refs = []
            for ref_item in references:
                path = ref_item["path"]
                path = path.replace("\\", "/")  # always use unix-style paths
                text_refs.append(
                    "\\begin{{quote}} \\verb|{r}|\\end{{quote}}".format(r=path)
                )
            return "\n".join(ref for ref in text_refs)

    def format_links(self, items, linkify):
        """Format a list of linked items in LaTeX."""
        links = []
        for item in items:
            link = self.format_item_link(item, linkify=linkify)
            links.append(link)
        return ", ".join(links)

    def format_item_link(self, item, linkify=True):
        """Format an item link in LaTeX."""
        if linkify and is_item(item):
            if item.header:
                return "\\hyperref[{u}]{{{u}}}".format(u=item.uid)
            return "\\hyperref[{u}]{{{u}}}".format(u=item.uid)
        else:
            return str(item.uid)  # if not `Item`, assume this is an `UnknownItem`

    def format_label_links(self, label, links, linkify):
        """Join a string of label and links with formatting."""
        if linkify:
            return "\\textbf{{{lb}}} {ls}".format(lb=label, ls=links)
        else:
            return "\\textbf{{{lb} {ls}}}".format(lb=label, ls=links)

    def _typeset_latex_table(
        self, table_match, text, i, line, block, table_found, header_done, end_pipes
    ):
        """Typeset tables."""
        if not table_found:
            table_found, header_done, line, end_pipes = _check_for_new_table(
                table_match, text, i, line, block, table_found, header_done, end_pipes
            )
        else:
            if not header_done:
                line = self.HLINE
                header_done = True
            else:
                # Fix the line.
                line = _fix_table_line(line, end_pipes)
        return table_found, header_done, line, end_pipes

    def _format_href_text(self, text):
        """Fix the href text related issues being seen."""
        output_line = ""
        for i, line in enumerate(text):
            if "](" in line:
                # Check if there are text that is using brackets but not a href reference
                # TODO: adjust this def to be more flexible 
                href_count = line.count("](")
                bracket_count = line.count("[")
                log.info(f'Number of hrefs detacted',href_count)
                log.debug(f'Number of [ in line',bracket_count)
                if href_count != bracket_count:
                    warning = "Get rid of text that had `[]s` and are not hrefs in requirement details."
                    log.warning(warning)
                    yield warning
                else:
                    split_line_text = line.split("[")
                    # Text before the link
                    text = str(split_line_text[0])
                    text = text.replace("_", "\\_")
                    # Rest of line / unformatted with no text part
                    remainder = str(split_line_text[1])
                    split_link_prefix = remainder.split("](")
                    split_link = str(split_link_prefix[1]).split(")")
                    # Markdown URL prefix
                    url_prefix = "{" + str(split_link_prefix[0]) + "}"
                    link = "{" + str(split_link[0]) + "}"
                    url_prefix = url_prefix.replace("_", "\\_")
                    rest_text = str(split_link[1]).replace("_", "\\_")
                    output_line = text + "\\href" + link + url_prefix + rest_text
                    yield output_line
            if "<br>" in line:
                output_line = line.replace("<br> <br>", "\\par ").replace("<br><br>", "\\par ").replace("<br>", "\\par")
                yield output_line.replace("^", "\\^").replace("_", "\\_")
            else:
                output_line = line.replace("^", "\\^").replace("_", "\\_")
                yield output_line


    def _format_latex_text(self, text):
        """Fix all general text formatting to use LaTeX-macros."""
        block: List[str]
        block = []
        environment_data = {}
        environment_data["table_found"] = False
        header_done = False
        environment_data["code_found"] = False
        math_found = False
        environment_data["plantuml_found"] = False
        plantuml_file = ""
        plantuml_name = ""
        plantuml_count = 0
        end_pipes = False

        for i, line in enumerate(text):

            #############################
            ## Fix plantuml.
            #############################
            if environment_data["plantuml_found"]:
                no_paragraph = True
            if re.findall("^`*plantuml\\s", line):
                plantuml_count = plantuml_count + 1
                plantuml_title = re.search('title="(.*)"', line)
                if plantuml_title:
                    plantuml_name = str(plantuml_title.groups(0)[0])
                else:
                    raise DoorstopError(
                        "'title' is required for plantUML processing in LaTeX."
                    )
                plantuml_file = re.sub("\\s", "-", plantuml_name)
                block.append(
                    r"\hyperref[fig:plant"
                    + str(plantuml_count)
                    + "]{"
                    + plantuml_name
                    + "}"
                )
                line = "\\begin{plantuml}{" + plantuml_file + "}"
                environment_data["plantuml_found"] = True
            if re.findall("@enduml", line):
                block.append(line)
                block.append("\\end{plantuml}")
                line = (
                    "\\process{"
                    + plantuml_file
                    + "}{0.8\\textwidth}{"
                    + plantuml_name
                    + "}"
                    + "{"
                    + str(plantuml_count)
                    + "}"
                )
                environment_data["plantuml_found"] = False
            # Skip the rest since we are in a plantuml block!
            if environment_data["plantuml_found"]:
                block.append(line)
                # Check for end of file and end all environments.
                self._check_for_eof(
                    i,
                    block,
                    text,
                    environment_data,
                    plantuml_name,
                    plantuml_file,
                )
                continue

            #############################
            ## Fix code blocks.
            #############################
            code_match = re.findall("```", line)
            if environment_data["code_found"]:
                no_paragraph = True
            if code_match:
                # Check previous line of @enduml.
                if i > 0:
                    previous_line = text[i - 1]
                    if re.findall("@enduml", previous_line):
                        continue
                if environment_data["code_found"]:
                    line = "\\end{lstlisting}"
                    environment_data["code_found"] = False
                else:
                    # Check for language.
                    language = re.search("```(.*)", line)
                    if language and str(language.groups(0)[0]) != "":
                        line = (
                            "\\begin{lstlisting}[language="
                            + str(language.groups(0)[0])
                            + "]"
                        )
                    else:
                        line = "\\begin{lstlisting}"
                    environment_data["code_found"] = True
            # Skip the rest since we are in a code block!
            if environment_data["code_found"]:
                block.append(line)
                # Check for end of file and end all environments.
                self._check_for_eof(
                    i,
                    block,
                    text,
                    environment_data,
                    plantuml_name,
                    plantuml_file,
                )
                continue
            # Replace ` for inline code, but not if it is already escaped.
            # First replace escaped inline code.
            line = re.sub("\\\\`", "##!!TEMPINLINE!!##", line)
            # Then replace inline code.
            line = re.sub("`(.+?)`", "\\\\lstinline`\\1`", line)
            # Then replace escaped inline code back.
            line = re.sub("##!!TEMPINLINE!!##", "\\\\`{}", line)

            #############################
            ## Fix images.
            #############################
            image_match = re.findall(r"!\[(.*)\]\((.*)\)", line)
            if image_match:
                line = _typeset_latex_image(image_match, line, block)
            #############################
            ## Fix $ and MATH.
            #############################
            math_match = re.split("\\$\\$", line)
            if len(math_match) > 1:
                if math_found and len(math_match) == 2:
                    math_found = False
                    line = math_match[0] + "$" + _latex_convert(math_match[1])
                elif len(math_match) == 2:
                    math_found = True
                    line = _latex_convert(math_match[0]) + "$" + math_match[1]
                elif len(math_match) == 3:
                    line = (
                        _latex_convert(math_match[0])
                        + "$"
                        + math_match[1]
                        + "$"
                        + _latex_convert(math_match[2])
                    )
                else:
                    raise DoorstopError(
                        "Cannot handle multiple math environments on one row."
                    )
            else:
                line = _latex_convert(line)
            # Skip all other changes if in MATH!
            if math_found:
                line = line + "\\\\"
                block.append(line)
                continue
            #############################
            ## Fix lists.
            #############################
            # Check if we are at the end of the data.
            if i == len(text) - 1:
                next_line = ""
            else:
                next_line = text[i + 1]
            (no_paragraph, processed_block, line) = self.process_lists(line, next_line)
            if processed_block != "":
                block.append(processed_block)
            #############################
            ## Fix tables.
            #############################
            # Check if line is part of table.
            table_match = re.findall("\\|", line)
            if table_match:
                (
                    environment_data["table_found"],
                    header_done,
                    line,
                    end_pipes,
                ) = self._typeset_latex_table(
                    table_match,
                    text,
                    i,
                    line,
                    block,
                    environment_data["table_found"],
                    header_done,
                    end_pipes,
                )
            else:
                if environment_data["table_found"]:
                    block.append(self.END_LONGTABLE)
                environment_data["table_found"] = False
                header_done = False

            # Look ahead for empty line and add paragraph.
            if i < len(text) - 1:
                next_line = text[i + 1]
                if next_line == "" and not re.search("\\\\", line) and not no_paragraph:
                    line = line + "\\\\"

            #############################
            ## All done. Add the line.
            #############################
            block.append(line)

            # Check for end of file and end all environments.
            self._check_for_eof(
                i,
                block,
                text,
                environment_data,
                plantuml_name,
                plantuml_file,
            )
        return block

    def _check_for_eof(
        self,
        index,
        block,
        text,
        environment_data,
        plantuml_name,
        plantuml_file,
    ):
        """Check for end of file and end all unended environments."""
        if index == len(text) - 1:
            if environment_data["code_found"]:
                block.append("\\end{lstlisting}")
            if environment_data["plantuml_found"]:
                block.append("\\end{plantuml}")
                block.append(
                    "\\process{"
                    + plantuml_file
                    + "}{0.8\\textwidth}{"
                    + plantuml_name
                    + "}"
                )
            if environment_data["table_found"]:
                block.append(self.END_LONGTABLE)

    def create_matrix(self, directory):
        """Create a traceability table for LaTeX."""
        # Setup.
        table = self.object.get_traceability().__iter__()
        traceability = []
        file = os.path.join(directory, "traceability.tex")
        count = 0
        # Start the table.
        table_start = "\\begin{longtable}{"
        table_head = ""
        header_data = table.__next__()
        for column in header_data:
            count = count + 1
            table_start = table_start + "|l"
            if len(table_head) > 0:
                table_head = table_head + " & "
            header = str(column).split("-")[0]
            print(header)
            table_head = table_head + "\\textbf{" + header + "}"
        table_start = table_start + "|}\\\\"
        table_head = table_head + ""
        traceability.append(table_start)
        traceability.append(
            "\\caption{Traceability matrix.}\\label{tbl:trace}\\zlabel{tbl:trace}\\\\"
        )
        #traceability.append(self.HLINE)
        traceability.append(table_head)
        #traceability.append(self.HLINE)
        traceability.append("\\endfirsthead")
        traceability.append("\\caption{\\textit{(Continued)} Traceability matrix.}\\\\ \\hline")
        #traceability.append(self.HLINE)
        traceability.append(table_head)
        #traceability.append(self.HLINE)
        traceability.append("\\endhead")
        #traceability.append(self.HLINE)
        traceability.append(
            "\\multicolumn{{{n}}}{{r}}{{\\textit{{Continued on next page.}}}}\\\\".format(
                n=count
            )
        )
        traceability.append("\\endfoot")
        #traceability.append(self.HLINE)
        traceability.append("\\endlastfoot")
        # Add rows.
        for row in table:
            row_text = ""
            for column in row:
                if len(row_text) > 0:
                    row_text = row_text + " & "
                if column:
                    row_text = row_text + "\\hyperref[{u}]{{{u}}}".format(u=str(column))
                else:
                    row_text = row_text + " "
            row_text = row_text + "\\\\ \\hline"
            traceability.append(row_text)
            #traceability.append(self.HLINE)
        # End the table.
        traceability.append(self.END_LONGTABLE)
        common.write_lines(traceability, file, end=settings.WRITE_LINESEPERATOR)

    def _get_compile_path(self):
        """Return the path to the compile script."""
        head, tail = os.path.split(self.path)
        # If tail ends with .tex, replace it with compile.sh.
        if tail.endswith(".tex"):
            return os.path.join(head, "compile.sh")
        return os.path.join(self.path, "compile.sh")

    def _generate_latex_wrapper(self):
        """Generate all wrapper scripts required for typesetting in LaTeX."""
        # Check for defined document attributes.
        doc_attributes = get_document_attributes(self.document)
        # Create the wrapper file.
        head, tail = os.path.split(self.documentPath)
        if tail != extract_prefix(self.document) + ".tex":
            log.warning(
                "LaTeX export does not support custom file names. Change in .doorstop.yml instead."
            )
        #tail = doc_attributes["name"] + ".tex"
        tail = "Requirements.tex"
        self.documentPath = os.path.join(head, extract_prefix(self.document) + ".tex")
        wrapperPath = os.path.join(head, tail)
        # Load template data.
        templatePath = os.path.abspath(os.path.join(self.assetsPath, "..", "template"))
        log.info(
            "Loading template data from {}/{}.yml".format(templatePath, self.template)
        )
        template_data = read_template_data(self.assetsPath, self.template)
        check_latex_template_data(
            template_data, "{}/{}.yml".format(templatePath, self.template)
        )
        wrapper = []
        wrapper.append(
            "\\documentclass[%s]{template/%s}"
            % (", ".join(template_data["documentclass"]), self.template)
        )
        # Add required packages.
        wrapper = _add_comment(
            wrapper,
            "These packages are required.",
        )
        wrapper.append("\\usepackage{enumitem}")
        wrapper = _add_comment(wrapper, "END required packages.")
        wrapper.append("")

        # Add required packages from template data.
        wrapper = _add_comment(
            wrapper,
            "These packages were automatically added from the template configuration file.",
        )
        for package, options in template_data["usepackage"].items():
            package_line = "\\usepackage"
            if options:
                package_line += "[%s]" % ", ".join(options)
            package_line += "{%s}" % package
            wrapper.append(package_line)
        wrapper = _add_comment(
            wrapper, "END data from the template configuration file."
        )
        wrapper.append("")
        wrapper = _add_comment(
            wrapper,
            "These fields are generated from the default doc attribute in the .doorstop.yml file.",
        )
        wrapper.append(
            "\\def\\doccopyright{{{n}}}".format(
                n=_latex_convert(doc_attributes["copyright"])
            )
        )
        wrapper.append(
            "\\def\\doccategory{{{t}}}".format(
                t=_latex_convert(extract_prefix(self.document))
            )
        )
        #wrapper.append(
        #    "\\def\\doctitle{{{n}}}".format(n=_latex_convert(doc_attributes["title"]))
        #)
        wrapper.append(
            "\\def\\docref{{{n}}}".format(n=_latex_convert(doc_attributes["ref"]))
        )
        wrapper.append(
            "\\def\\docby{{{n}}}".format(n=_latex_convert(doc_attributes["by"]))
        )
        wrapper.append(
            "\\def\\docissuemajor{{{n}}}".format(
                n=_latex_convert(doc_attributes["major"])
            )
        )
        wrapper.append(
            "\\def\\docissueminor{{{n}}}".format(
                n=_latex_convert(doc_attributes["minor"])
            )
        )
        wrapper = _add_comment(wrapper, "END data from the .doorstop.yml file.")
        wrapper.append("")

        wrapper = _add_comment(
            wrapper,
            "LaTex is limited to four (4) levels of lists. The following code extends this to nine (9) levels.",
        )
        wrapper.append("% ******************************************************")
        wrapper.append("% Increase nesting level for lists")
        wrapper.append("% ******************************************************")
        wrapper.append("\\setlistdepth{9}")
        wrapper.append("\\newlist{itemizeDeep}{enumerate}{9}")
        wrapper.append("\\setlist[itemizeDeep,1]{label=\\textbullet}")
        wrapper.append(
            "\\setlist[itemizeDeep,2]{label=\\normalfont\\bfseries \\textendash}"
        )
        wrapper.append("\\setlist[itemizeDeep,3]{label=\\textasteriskcentered}")
        wrapper.append("\\setlist[itemizeDeep,4]{label=\\textperiodcentered}")
        wrapper.append("\\setlist[itemizeDeep,5]{label=\\textopenbullet}")
        wrapper.append("\\setlist[itemizeDeep,6]{label=\\textbullet}")
        wrapper.append(
            "\\setlist[itemizeDeep,7]{label=\\normalfont\\bfseries \\textendash}"
        )
        wrapper.append("\\setlist[itemizeDeep,8]{label=\\textasteriskcentered}")
        wrapper.append("\\setlist[itemizeDeep,9]{label=\\textperiodcentered}")
        wrapper.append("\\newlist{enumerateDeep}{enumerate}{9}")
        wrapper.append("\\setlist[enumerateDeep]{label*=\\arabic*.}")
        wrapper = _add_comment(wrapper, "END list depth fix.")
        wrapper.append("")

        ## Previous external link referencing.
        # for external, _ in iter_documents(self.object, self.path, ".tex"):
        #     # Check for defined document attributes.
        #     external_doc_attributes = get_document_attributes(external)
        #     # Don't add self.
        #     if external_doc_attributes["name"] != doc_attributes["name"]:
        #         if not info_text_set:
        #             wrapper = _add_comment(
        #                 wrapper,
        #                 "These are automatically added external references to make cross-references work between the PDFs.",
        #             )
        #             info_text_set = True
        #         wrapper.append(
        #             "\\zexternaldocument{{{n}}}".format(
        #                 n=external_doc_attributes["name"]
        #             )
        #         )
        #         wrapper.append(
        #             "\\externaldocument{{{n}}}".format(
        #                 n=external_doc_attributes["name"]
        #             )
        #         )

        wrapper = _add_comment(
            wrapper,
            "These lines were automatically added from the template configuration file to allow full customization of the template _before_ \\begin{document}.",
        )
        for line in template_data["before_begin_document"]:
            wrapper.append(line)
        wrapper = _add_comment(
            wrapper, "END custom data from the template configuration file."
        )
        wrapper.append("")
        wrapper.append("\\begin{document}")
        wrapper = _add_comment(
            wrapper,
            "These lines were automatically added from the template configuration file to allow full customization of the template _after_ \\begin{document}.",
        )

        for line in template_data["after_begin_document"]:
            wrapper.append(line)
        wrapper = _add_comment(
            wrapper, "END custom data from the template configuration file."
        )
        wrapper.append("")

        # Adjusted link referencing for one document output (for doc-xx.tex)
        info_text_set = False
        wrapper = _add_comment(
            wrapper,
            "Loading all doorstop data files from external document attributes.",
        )
        for external, _ in iter_documents(self.object, self.path, ".tex"):
            # Check for defined document attributes.
            external_doc_attributes = extract_prefix(external)
            info_text_set = True
            wrapper.append(
                "\\input{{{n}.tex}}".format(n=external_doc_attributes)
            )
            wrapper.append("\\newpage")

        if info_text_set:
            wrapper = _add_comment(wrapper, "END doorstop data files.")
            wrapper.append("")

        graphics_present = False
        # To include graphics listed in yaml file after the beginning of the document but before the matrix.
        if "include_graphics" in template_data:
            for graphics, label in template_data["include_graphics"].items():
                graphics_present = True
                if label:
                    adjusted_label = str(label).replace("['", "").replace("']", "")
                    label_line = "\\section{" + adjusted_label + "}"
                else:
                    label_line = "section{Image_1}"
                wrapper.append(label_line)
                wrapper.append("\\begin{figure}[ht!]")
                wrapper.append("\\begin{center}")
                wrapper.append("\\includegraphics[angle=90, height=20cm, width=\\textwidth]{" + graphics + "}")
                wrapper.append("\\end{center}")
                wrapper.append("\\end{figure}")
                wrapper.append("\\newpage")
            wrapper = _add_comment(
                wrapper, "END data from the template configuration file."
            )
        else:
            wrapper = _add_comment(
                wrapper, "No graphics information in template to be added to published document. Skipping..."
            )
        wrapper.append("")

        if graphics_present:
            wrapper = _add_comment(
                wrapper, "No empty page needed before traceability matrix / graphics present."
            )
            wrapper.append("")
        else:
            wrapper = _add_comment(
                wrapper, "Adding empty page before traceability matrix"
            )
            # Add an empty page before the traceability matrix for graphs
            wrapper.append("")
            wrapper.append("\\newpage")
            wrapper.append("")

        # Include traceability matrix
        if "traceability_matrix" in template_data:
            wrapper = _add_comment(wrapper, "Add traceability matrix.")
            wrapper.append("\\section{Traceability Matrix}")
            wrapper.append("\\input{traceability.tex}")
            wrapper = _add_comment(wrapper, "END traceability matrix.")
            wrapper.append("")
            wrapper.append("\\newpage")
            wrapper.append("")
        else:
            wrapper = _add_comment(wrapper, "Traceability matrix import setting turned off in doorstop.yml. Skipping...")
            wrapper.append("")

        # Include rvm if setting is true
        if "rvm" in template_data:
            wrapper = _add_comment(wrapper, "Add rvm matrix.")
            wrapper.append("\\begin{landscape}")
            wrapper.append("\\section{Requirements Verification Matrix}")
            wrapper.append("\\csvreader[longtable=LLLLLL,table head=\\caption{Requirement Verification Matrix for L4 Requirements.}\\\\")
            wrapper.append("\\toprule\\bfseries UID & \\bfseries Name & \\bfseries Verification Plan & \\bfseries Method & \\bfseries Phase & \\bfseries Status \\\ \\midrule\\endhead")
            wrapper.append("\\bottomrule\\endfoot,")
            wrapper.append("late after line=\\\,")
            wrapper.append("]{rvm.csv}{}{\\csvcoli & \\csvcolii & \\csvcoliii & \\csvcoliv & \\csvcolv & \\csvcolvi}")
            wrapper.append("\\end{landscape}")
            wrapper = _add_comment(wrapper, "END rvm.")
            wrapper.append("")
        else:
            wrapper = _add_comment(wrapper, "RVM import setting turned off in doorstop.yml. Skipping...")
            wrapper.append("")

        # End the document command to be added
        wrapper.append("\\end{document}")
        common.write_lines(wrapper, wrapperPath, end=settings.WRITE_LINESEPERATOR)

        # Add to compile.sh as return value.
        compile_script = "xelatex -interaction=nonstopmode Requirements.tex"

        return compile_script
