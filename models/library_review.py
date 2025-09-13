from odoo import models, fields, api
from odoo.exceptions import ValidationError

class LibraryReview(models.Model):
    _name = 'library.review'
    _description = 'Book Review'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    name = fields.Char('Review Title', required=True)
    member_id = fields.Many2one('library.member', 'Reviewer', required=True)
    book_id = fields.Many2one('library.book', 'Book', required=True, ondelete='cascade')
    rating = fields.Integer('Rating', required=True)
    review_text = fields.Html('Review')
    review_date = fields.Date('Review Date', default=fields.Date.today)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('moderated', 'Under Moderation'),
        ('rejected', 'Rejected'),
    ], 'Status', default='draft', tracking=True)
    
    helpful_count = fields.Integer('Helpful Votes', default=0)
    verified_borrower = fields.Boolean('Verified Borrower', compute='_compute_verified_borrower')
    moderator_notes = fields.Text('Moderator Notes')

    _sql_constraints = [
        ('rating_check', 'CHECK(rating >= 1 AND rating <= 5)', 'Rating must be between 1 and 5!'),
        ('unique_member_book', 'UNIQUE(member_id, book_id)', 'A member can only review a book once!'),
    ]

    @api.depends('member_id', 'book_id')
    def _compute_verified_borrower(self):
        for review in self:
            borrowings = self.env['library.borrowing'].search([
                ('member_id', '=', review.member_id.id),
                ('book_id', '=', review.book_id.id),
                ('state', 'in', ['returned', 'borrowed'])
            ])
            review.verified_borrower = bool(borrowings)

    def action_publish(self):
        self.state = 'published'

    def action_moderate(self):
        self.state = 'moderated'

    def action_reject(self, reason):
        self.state = 'rejected'
        self.moderator_notes = reason

    def action_mark_helpful(self):
        self.helpful_count += 1