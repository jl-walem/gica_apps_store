import os

from odoo import models
from odoo.exceptions import UserError


class GicaTranslationMixin(models.AbstractModel):
    _name = 'gica.translation.mixin'
    _description = 'GICA Translation Mixin'

    def _gica_translate_po(self, message):

        lang = self.env.user.lang or self.env.context.get('lang') or 'en_US'

        po_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'i18n',
            '%s.po' % lang
        )

        if not os.path.exists(po_file):
            return message

        with open(po_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        target = 'msgid "%s"' % message.replace('"', '\\"')

        for index, line in enumerate(lines):
            if line.strip() == target:
                if index + 1 < len(lines):
                    next_line = lines[index + 1].strip()
                    if next_line.startswith('msgstr "'):
                        value = next_line[8:-1]
                        return value or message

        return message

    def _gica_error(self, message):

        raise UserError(
            self._gica_translate_po(message)
        )
