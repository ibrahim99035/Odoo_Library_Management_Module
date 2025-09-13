from odoo import models, fields, api
from odoo.exceptions import UserError

class BookTransferWizard(models.TransientModel):
    _name = 'book.transfer.wizard'
    _description = 'Book Transfer Wizard'

    book_id = fields.Many2one('library.book', 'Book', required=True)
    from_location = fields.Char('From Location', required=True)
    to_location = fields.Char('To Location', required=True)
    transfer_date = fields.Date('Transfer Date', default=fields.Date.today, required=True)

    def action_transfer_book(self):
        # Implement your transfer logic here
        if not self.book_id or not self.to_location:
            raise UserError('Please select a book and destination.')
        # Example: update book location
        self.book_id.location = self.to_location
        return {'type': 'ir.actions.act_window_close'}