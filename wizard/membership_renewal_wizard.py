from odoo import models, fields, api
from odoo.exceptions import UserError

class MembershipRenewalWizard(models.TransientModel):
    _name = 'membership.renewal.wizard'
    _description = 'Membership Renewal Wizard'

    member_id = fields.Many2one('library.member', 'Member', required=True)
    renewal_period = fields.Integer('Renewal Period (months)', required=True, default=12)
    new_expiry_date = fields.Date('New Expiry Date', compute='_compute_new_expiry_date')

    @api.depends('member_id', 'renewal_period')
    def _compute_new_expiry_date(self):
        for wizard in self:
            if wizard.member_id and wizard.renewal_period:
                wizard.new_expiry_date = fields.Date.add(wizard.member_id.expiry_date or fields.Date.today(), months=wizard.renewal_period)
            else:
                wizard.new_expiry_date = False

    def action_renew_membership(self):
        if not self.member_id:
            raise UserError('Please select a member.')
        if not self.new_expiry_date:
            raise UserError('Invalid renewal period.')
        self.member_id.expiry_date = self.new_expiry_date
        return {'type': 'ir.actions.act_window_close'}