from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta

class LibraryReservation(models.Model):
    _name = 'library.reservation'
    _description = 'Book Reservation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'reservation_date desc'

    name = fields.Char('Reservation Reference', compute='_compute_name', store=True)
    member_id = fields.Many2one('library.member', 'Member', required=True, tracking=True)
    book_id = fields.Many2one('library.book', 'Book', required=True, tracking=True)
    reservation_date = fields.Date('Reservation Date', default=fields.Date.today, required=True)
    expiry_date = fields.Date('Expiry Date', compute='_compute_expiry_date', store=True, tracking=True)
    
    state = fields.Selection([
        ('active', 'Active'),
        ('fulfilled', 'Fulfilled'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ], 'Status', default='active', tracking=True)
    
    priority = fields.Integer('Priority', default=1)
    queue_position = fields.Integer('Queue Position', compute='_compute_queue_position')
    notes = fields.Text('Notes')
    notification_sent = fields.Boolean('Notification Sent', default=False)
    fulfilled_date = fields.Date('Fulfilled Date')
    borrowing_id = fields.Many2one('library.borrowing', 'Related Borrowing')

    @api.depends('member_id', 'book_id', 'reservation_date')
    def _compute_name(self):
        for reservation in self:
            if reservation.member_id and reservation.book_id:
                reservation.name = f"{reservation.member_id.name} - {reservation.book_id.name}"
            else:
                reservation.name = "New Reservation"

    @api.depends('reservation_date')
    def _compute_expiry_date(self):
        config = self.env['library.config'].get_config()
        for reservation in self:
            if reservation.reservation_date:
                reservation.expiry_date = reservation.reservation_date + timedelta(days=config.reservation_expiry_days)

    @api.depends('book_id', 'reservation_date', 'priority')
    def _compute_queue_position(self):
        for reservation in self:
            if reservation.book_id and reservation.state == 'active':
                prior_reservations = self.search_count([
                    ('book_id', '=', reservation.book_id.id),
                    ('state', '=', 'active'),
                    '|',
                    ('priority', '>', reservation.priority),
                    '&',
                    ('priority', '=', reservation.priority),
                    ('reservation_date', '<', reservation.reservation_date)
                ])
                reservation.queue_position = prior_reservations + 1
            else:
                reservation.queue_position = 0

    def action_fulfill(self):
        if self.state != 'active':
            raise UserError("Only active reservations can be fulfilled!")
        
        # Create borrowing record
        borrowing = self.env['library.borrowing'].create({
            'member_id': self.member_id.id,
            'book_id': self.book_id.id,
            'borrow_date': fields.Date.today(),
        })
        
        self.state = 'fulfilled'
        self.fulfilled_date = fields.Date.today()
        self.borrowing_id = borrowing.id
        self.message_post(body="Reservation fulfilled and book borrowed")

    def action_cancel(self):
        self.state = 'cancelled'
        self.message_post(body="Reservation cancelled")

    def action_notify_member(self):
        # Send notification to member that book is available
        template = self.env.ref('library_management.mail_template_book_available')
        template.send_mail(self.id, force_send=True)
        self.notification_sent = True

    @api.model
    def _cron_check_expired_reservations(self):
        """Cron job to mark expired reservations"""
        expired_reservations = self.search([
            ('state', '=', 'active'),
            ('expiry_date', '<', fields.Date.today())
        ])
        expired_reservations.write({'state': 'expired'})

    @api.model
    def _cron_notify_available_books(self):
        """Cron job to notify members when reserved books become available"""
        available_reservations = self.search([
            ('state', '=', 'active'),
            ('notification_sent', '=', False),
            ('book_id.available_copies', '>', 0)
        ])
        
        for reservation in available_reservations:
            if reservation.queue_position == 1:  # First in queue
                reservation.action_notify_member()