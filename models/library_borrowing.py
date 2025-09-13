from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import date, timedelta

class LibraryBorrowing(models.Model):
    _name = 'library.borrowing'
    _description = 'Book Borrowing'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'borrow_date desc'

    name = fields.Char('Borrowing Reference', compute='_compute_name', store=True)
    
    member_id = fields.Many2one('library.member', 'Member', required=True, tracking=True)
    book_id = fields.Many2one('library.book', 'Book', required=True, tracking=True)
    
    borrow_date = fields.Date('Borrow Date', default=fields.Date.today, required=True, tracking=True)
    due_date = fields.Date('Due Date', compute='_compute_due_date', store=True, tracking=True)
    return_date = fields.Date('Return Date', tracking=True)
    
    state = fields.Selection([
        ('borrowed', 'Borrowed'),
        ('returned', 'Returned'),
        ('overdue', 'Overdue'),
        ('lost', 'Lost'),
    ], 'Status', default='borrowed', tracking=True)
    
    renewal_count = fields.Integer('Renewals', default=0, tracking=True)
    
    max_renewals = fields.Integer('Max Renewals', compute='_compute_max_renewals')
    can_renew = fields.Boolean('Can Renew', compute='_compute_can_renew')
    
    fine_amount = fields.Float('Fine Amount', compute='_compute_fine_amount', store=True)
    days_overdue = fields.Integer('Days Overdue', compute='_compute_days_overdue')
    
    notes = fields.Text('Notes')
    
    # librarian_id & return_librarian_id are set to current user by default 
    # 'res.users' is the built-in Odoo model for users
    librarian_id = fields.Many2one('res.users', 'Librarian', default=lambda self: self.env.user)
    return_librarian_id = fields.Many2one('res.users', 'Return Librarian')
    
    # Condition fields to track book condition at borrow and return
    book_condition_borrow = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ], 'Condition at Borrow', default='good')
    
    book_condition_return = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('damaged', 'Damaged'),
    ], 'Condition at Return')
    
    # Relation to fines - borrowing_id is the Many2one field in library.fine
    # fine_ids will hold all fines related to this borrowing
    fine_ids = fields.One2many('library.fine', 'borrowing_id', 'Related Fines')

    # Ensure a member cannot borrow the same book twice simultaneously
    _sql_constraints = [
        ('unique_active_borrowing', 'EXCLUDE (book_id WITH =, member_id WITH =) WHERE (state = \'borrowed\')',
         'A member cannot borrow the same book twice simultaneously!'),
    ]

    # Compute method to generate a unique name for each borrowing record
    @api.depends('member_id', 'book_id', 'borrow_date')
    def _compute_name(self):
        for record in self:
            if record.member_id and record.book_id:
                record.name = f"{record.member_id.name} - {record.book_id.name}"
            else:
                record.name = "New Borrowing"

    # Compute due date based on borrow date and library configuration
    @api.depends('borrow_date')
    def _compute_due_date(self):
        config = self.env['library.config'].get_config()
        for record in self:
            if record.borrow_date:
                record.due_date = record.borrow_date + timedelta(days=config.max_borrow_days)
    
    # Compute maximum renewals allowed from configuration 
    @api.depends('member_id')
    def _compute_max_renewals(self):
        config = self.env['library.config'].get_config()
        for record in self:
            record.max_renewals = config.max_renewals

    # Compute if the borrowing can be renewed
    @api.depends('renewal_count', 'max_renewals', 'state')
    def _compute_can_renew(self):
        for record in self:
            record.can_renew = (record.state == 'borrowed' and 
                              record.renewal_count < record.max_renewals and
                              not record.book_id.reservation_ids.filtered(lambda r: r.state == 'active'))

    # Compute days overdue
    @api.depends('due_date', 'return_date', 'state')
    def _compute_days_overdue(self):
        for record in self:
            if record.state == 'overdue' or (record.state == 'returned' and record.return_date):
                end_date = record.return_date or date.today()
                if record.due_date and end_date > record.due_date:
                    record.days_overdue = (end_date - record.due_date).days
                else:
                    record.days_overdue = 0
            else:
                record.days_overdue = 0

    # Compute fine amount based on days overdue and configuration
    @api.depends('days_overdue')
    def _compute_fine_amount(self):
        config = self.env['library.config'].get_config()
        for record in self:
            if record.days_overdue > 0:
                record.fine_amount = record.days_overdue * config.fine_per_day
            else:
                record.fine_amount = 0.0

    # Override create and write to enforce borrowing constraints
    @api.model
    def create(self, vals):
        borrowing = super().create(vals) # Call the original create method and store the result
        borrowing._check_borrowing_constraints() # Check constraints after creation
        return borrowing

    def write(self, vals):
        result = super().write(vals)
        if 'member_id' in vals or 'book_id' in vals:
            self._check_borrowing_constraints()
        return result

    def _check_borrowing_constraints(self):
        for record in self:
            # Check if member can borrow
            can_borrow, message = record.member_id.can_borrow_book()
            if not can_borrow and record.state == 'borrowed':
                raise ValidationError(f"Cannot borrow book: {message}")
            
            # Check if book is available
            if not record.book_id.check_availability() and record.state == 'borrowed':
                raise ValidationError("Book is not available for borrowing!")

    def action_renew(self):
        if not self.can_renew:
            raise UserError("Cannot renew this book!")
        
        config = self.env['library.config'].get_config()
        self.renewal_count += 1
        self.due_date = self.due_date + timedelta(days=config.max_borrow_days)
        self.message_post(body=f"Book renewed. New due date: {self.due_date}")

    def action_return(self):
        if self.state not in ['borrowed', 'overdue']:
            raise UserError("Only borrowed or overdue books can be returned!")
        
        self.return_date = fields.Date.today()
        self.return_librarian_id = self.env.user
        self.state = 'returned'
        
        # Create fine if overdue
        if self.fine_amount > 0:
            self.env['library.fine'].create({
                'member_id': self.member_id.id,
                'borrowing_id': self.id,
                'amount': self.fine_amount,
                'reason': 'late_return',
                'date_created': fields.Date.today(),
            })
        
        self.message_post(body=f"Book returned on {self.return_date}")

    def action_mark_lost(self):
        self.state = 'lost'
        # Create fine for lost book
        self.env['library.fine'].create({
            'member_id': self.member_id.id,
            'borrowing_id': self.id,
            'amount': self.book_id.price or 50.0,  # Default fine for lost book
            'reason': 'lost',
            'date_created': fields.Date.today(),
        })

    @api.model
    def _cron_check_overdue_books(self):
        """Cron job to mark books as overdue"""
        overdue_borrowings = self.search([
            ('state', '=', 'borrowed'),
            ('due_date', '<', date.today())
        ])
        overdue_borrowings.write({'state': 'overdue'})