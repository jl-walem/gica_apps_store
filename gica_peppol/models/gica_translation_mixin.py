import ast
import os

from odoo import models
from odoo.exceptions import UserError


class GicaTranslationMixin(models.AbstractModel):
    _name = 'gica.peppol.translation.mixin'
    _description = 'GICA Peppol Translation Mixin'

    def _gica_translate_po(self, message):

        lang = self.env.user.lang or self.env.context.get('lang') or 'en_US'

        po_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'i18n',
            '%s.po' % lang
        )

        if not os.path.exists(po_file):
            return message

        def read_po_value(lines, index):
            line = lines[index].strip()

            if line.endswith('""'):
                index += 1
                value = ""
                while index < len(lines):
                    current = lines[index].strip()
                    if not current.startswith('"'):
                        break
                    value += ast.literal_eval(current)
                    index += 1
                return value, index

            value = line.split(" ", 1)[1]
            return ast.literal_eval(value), index + 1

        with open(po_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        index = 0
        while index < len(lines):
            line = lines[index].strip()

            if line.startswith("msgid "):
                msgid, index = read_po_value(lines, index)

                if msgid == message:
                    while index < len(lines):
                        line = lines[index].strip()

                        if line.startswith("msgstr "):
                            msgstr, index = read_po_value(lines, index)
                            return msgstr or message

                        if line.startswith("msgid "):
                            break

                        index += 1

                continue

            index += 1

        return message

    def _gica_error(self, message):

        raise UserError(
            self._gica_translate_po(message)
        )
