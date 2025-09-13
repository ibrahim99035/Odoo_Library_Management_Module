from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_library_member = fields.Boolean('Is Library Member', default=False)
    library_member_id = fields.Many2one('library.member', 'Library Member')
    
    @api.model
    def create(self, vals):
        partner = super().create(vals)
        if vals.get('is_library_member'):
            member = self.env['library.member'].create({
                'name': partner.name,
                'email': partner.email,
                'phone': partner.phone,
                'address': partner.street,
                'partner_id': partner.id,
            })
            partner.library_member_id = member.id
        return partner