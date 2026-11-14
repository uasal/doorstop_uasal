# SPDX-License-Identifier: LGPL-3.0-only

"""Functions to publish documents and items."""

import os
from re import sub

from doorstop import common, settings
from doorstop.core.publishers.base import BasePublisher, format_level
from doorstop.core.template import MATRIX
from doorstop.core.types import UID, is_item, iter_items

log = common.logger(__name__)


class MarkdownPublisher(BasePublisher):
    """Markdown publisher."""

    def create_index(self, directory, index=None, extensions=(".md",), tree=None):
        """No index for Markdown."""

    def create_matrix(self, directory):
        """Create matrix for Markdown.

        :param directory: directory for matrix

        """
        ############################################################
        # Create the csv matrix
        ############################################################
        # Get path and format extension
        filename = MATRIX
        path = os.path.join(directory, filename)

        # Create the matrix
        log.info("creating an {}...".format(filename))
        content = self._matrix_content()
        common.write_csv(content, path)

        ############################################################
        # Create the Markdown matrix
        ############################################################
        filename = MATRIX.replace(".csv", ".md")
        path = os.path.join(directory, filename)
        log.info("creating an {}...".format(filename))
        lines = self.lines_matrix()
        markdown = "\n".join(lines)
        common.write_text(markdown, path)

    # def lines_rvm(self, obj, **kwargs):
    #     """Requirements Verification Matrix Lines"""
    #     # title
    #     title = '# Requirements Verification Matrix'
    #     yield title
    #     # header
    #     table_format = "| --------- |"
    #     table_adjustments = "---------- |"
    #     count = 0
    #     linkify = kwargs.get("linkify", False)
    #     to_html = kwargs.get("to_html", False)
    #
    #     # header data / table start
    #     for item in iter_items(obj):
    #         if item.

    def lines_matrix(self, **kwargs):
        """Traceability table for markdown output."""
        # title
        title = "# Traceability Matrix"
        yield title
        # header
        table_format = "| ------------ |"
        table_adjustments = "------------ |"
        count = 0
        header_links = ""
        # header data / table start
        for document in self.object:  # pylint: disable=not-an-iterable
            link = "[{p}]({p}.md)".format(p=document.prefix)
            header_links = header_links + "{link} |".format(link=link)
            if count > 0:
                table_format = table_format + table_adjustments
            count = count + 1
        yield "| " + header_links + "\n" + table_format

        # data
        linkify = kwargs.get("linkify", False)
        for index, row in enumerate(self.object.get_traceability()):
            link = ""
            row_count = 0
            for item in row:
                if item is None and row_count > 0:
                    link = link + " | "
                elif item is None and row_count == 0:
                    link = "| "
                else:
                    link = link + " | " + self.format_item_link(item, linkify) + ""
                row_count = row_count + 1
            yield link

    def format_attr_list(self, item, linkify):
        """Create a Markdown attribute list for a heading."""
        return " {{#{u}}}".format(u=item.uid) if linkify else ""

    def format_ref(self, item):
        """Format an external reference in Markdown."""
        if settings.CHECK_REF:
            path, line = item.find_ref()
            path = path.replace("\\", "/")  # always use unix-style paths
            if line:
                return "> `{p}` (line {line})".format(p=path, line=line)
            else:
                return "> `{p}`".format(p=path)
        else:
            return "> '{r}'".format(r=item.ref)

    def format_references(self, item):
        """Format an external reference in Markdown."""
        if settings.CHECK_REF:
            references = item.find_references()
            text_refs = []
            for ref_item in references:
                path, line = ref_item
                path = path.replace("\\", "/")  # always use unix-style paths

                if line:
                    text_refs.append("> `{p}` (line {line})".format(p=path, line=line))
                else:
                    text_refs.append("> `{p}`".format(p=path))

            return "\n".join(ref for ref in text_refs)
        else:
            references = item.references
            text_refs = []
            for ref_item in references:
                path = ref_item["path"]
                path = path.replace("\\", "/")  # always use unix-style paths
                text_refs.append("> '{r}'".format(r=path))
            return "\n".join(ref for ref in text_refs)

    def format_links(self, items, linkify):
        """Format a list of linked items in Markdown."""
        links = []
        for item in items:
            link = self.format_item_link(item, linkify=linkify)
            links.append(link)
        return ", ".join(links)

    def format_item_link(self, item, linkify=True):
        """Format an item link in Markdown."""
        link = clean_link("{u}".format(u=self._generate_heading_from_item(item)))
        if linkify and is_item(item):
            if item.header:
                return "[{u} {h}]({p}.md#{l})".format(
                    u=item.uid, l=link, h=item.header, p=item.document.prefix
                )
            return "[{u}]({p}.md#{l})".format(
                u=item.uid, l=link, p=item.document.prefix
            )
        else:
            return "[{u}]({p}.md#{l})".format(
                u=item.uid, l=link, p=item.document.prefix
            )

    def format_label_links(self, label, links, linkify):
        """Join a string of label and links with formatting."""
        if linkify:
            return "*{lb}* {ls}".format(lb=label, ls=links)
        else:
            return "*{lb} {ls}*".format(lb=label, ls=links)

    def table_of_contents(self, linkify=None, obj=None):
        """Generate a table of contents for a Markdown document."""

        toc = "# Table of Contents\n\n"
        toc_doc = obj

        for item in iter_items(toc_doc):
            if item.depth == 1:
                prefix = " * "
            else:
                prefix = "    " * (item.depth - 1)
                prefix += "* "

            # Check if item has the attribute heading.
            if item.heading:
                lines = item.text.splitlines()
                heading = lines[0] if lines else ""
            elif item.header:
                heading = "{h}- _{u}_".format(h=item.header, u=item.uid)
            # Check if item has a 'short name' / treat as a header
            elif item.short_name:
                heading = "**{u}**- _{s}_".format(u=item.uid, s=item.short_name)
            else:
                heading = item.uid

            if settings.PUBLISH_HEADING_LEVELS:
                level = format_level(item.level)
                lbl = "{lev} {h}".format(lev=level, h=heading)
            else:
                lbl = heading

            if linkify:
                link = clean_link(self._generate_heading_from_item(item))
                line = "{p}[{lbl}](#{l})\n".format(p=prefix, lbl=lbl, l=link)
            else:
                line = "{p}{lbl}\n".format(p=prefix, lbl=lbl)
            toc += line
        return toc + "\n------------------"

    def lines(self, obj, **kwargs):
        """Yield lines for a Markdown report.

        :param obj: Item, list of Items, or Document to publish
        :param linkify: turn links into hyperlinks

        :return: iterator of lines of text

        """
        linkify = kwargs.get("linkify", False)
        toc = kwargs.get("toc", False)
        if toc:
            yield self.table_of_contents(linkify=linkify, obj=obj)

        yield from self._lines_markdown(obj, **kwargs)

    def _generate_heading_from_item(self, item, to_html=False):
        """Generate a heading from an item in a consistent way for Markdown.

        This ensures that references between documents are consistent.
        """
        result = ""
        heading = "##" * item.depth
        level = format_level(item.level)
        if item.heading:
            text_lines = item.text.splitlines()
            if item.header:
                text_lines.insert(0, item.header)
            # Level and Text
            if settings.PUBLISH_HEADING_LEVELS:
                standard = "{h} {lev} {t}".format(
                    h=heading, lev=level, t=text_lines[0] if text_lines else ""
                )
            else:
                standard = "{h} {t}".format(
                    h=heading, t=text_lines[0] if text_lines else ""
                )
            attr_list = self.format_attr_list(item, True)
            result = standard + attr_list
        else:
            uid = item.uid
            if settings.ENABLE_HEADERS:
                # <span class="anchor" id="L3-0024-Payload Metrology"></span><div id="L3-0024-Payload Metrology"></div>
                if to_html:
                    header = "{u}-<small><i>{s}</i></small>".format(
                        u=item.uid, s=item.short_name
                    )
                    span = "<span class='anchor' id='{u}-{s}'></span><div id='{u}-{s}'></div>".format(
                        u=item.uid, s=item.short_name
                    )
                    uid = span + header
                else:
                    uid = "{u}- _{s}_".format(u=item.uid, s=item.short_name)
            else:
                uid = "{u}".format(u=item.uid)

            # Level and UID
            if settings.PUBLISH_BODY_LEVELS:
                standard = "{h} {lev} {u}".format(h=heading, lev=level, u=uid)
            else:
                standard = "{h} {u}".format(h=heading, u=uid)

            # attr_list = self.format_attr_list(item, True)
            result = standard  # + attr_list
        return result

    def _lines_markdown(self, obj, **kwargs):
        """Yield lines for a Markdown report.

        :param obj: Item, list of Items, or Document to publish
        :param linkify: turn links into hyperlinks

        :return: iterator of lines of text


        """
        linkify = kwargs.get("linkify", False)
        to_html = kwargs.get("to_html", False)
        item_count = 0
        prev_level = ""
        sub_category = ""
        prev_category = ""
        prev_subcategory = ""

        for item in iter_items(obj):

            level = format_level(item.level)
            prefix = item.document.prefix
            uid = str(item.uid)
            split_uid = uid.split("-")
            label_links = ""

            # 'Level' Header for each document w/separator
            if item_count == 0:
                if prefix.startswith("L0"):
                    yield "# *Level- 0*\n"
                else:
                    yield "# *Level- " + level + "*\n"
                yield "------------------------------------------------------------------------\n"

            # Creating subsections for each document based on adjusted levels
            if len(split_uid) == 4:
                found_prefix = str(split_uid[0])
                category = str(split_uid[1])
                sub_category = str(split_uid[2])
                if category != prev_category:
                    prev_category = category
                    prev_subcategory = sub_category
                    yield "## *" + category + "- " + sub_category + "*\n"
                elif sub_category != prev_subcategory:
                    prev_subcategory = sub_category
                    yield "## *" + category + "- " + sub_category + "*\n"

            # Create item heading.
            complete_heading = self._generate_heading_from_item(item, to_html=to_html)
            yield complete_heading

            # Text
            if item.text:
                yield ""  # break before text
                yield from item.text.splitlines()
                yield ""

            # Attributes Publish
            if item.document.publish:
                for attr in item.document.publish:
                    if not item.attribute(attr) or item.attribute(attr) == "":
                        continue
                    else:
                        yield "**" + attr.capitalize() + ":** " + item.attribute(
                            attr
                        ) + "\n"

            # Ref (old version)
            if item.ref:
                yield ""  # break before reference
                yield self.format_ref(item)
            # Reference
            if item.references:
                yield ""  # break before reference
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

            # Add custom publish attributes (Table format)
            # if item.document and item.document.publish:
            #     header_printed = False
            #     for attr in item.document.publish:
            #         if not item.attribute(attr):
            #             continue
            #         if not header_printed:
            #             header_printed = True
            #             yield ""
            #             yield "| Attribute | Value |"
            #             yield "| --------- | ----- |"
            #         yield "| {} | {} |".format(attr, item.attribute(attr))
            #     yield ""

            item_count = item_count + 1  # item counter
            yield "--------------------------------\n"  # break between items


def clean_link(uid):
    """Clean a UID for use in a link.

    1. Strip leading # and spaces.
    2. Only smallcaps are allowed.
    3. Spaces are replaced with hyphens.
    5. All other special characters are removed.
    """
    uid = sub(r"^#*\s*", "", uid)
    uid = uid.lower()
    uid = uid.replace(" ", "-")
    uid = sub("[^a-z0-9-]", "", uid)
    return uid
