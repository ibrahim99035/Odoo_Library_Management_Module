from odoo import models, fields, api, _

class ResUsers(models.Model):
    """Extends res.users with library member link and librarian flag."""
    _inherit = 'res.users'

    library_member_id = fields.Many2one(
        'library.member',
        string='Library Member',
        help='Related library member record for this user.'
    )
    is_librarian = fields.Boolean(
        string='Is Librarian',
        compute='_compute_is_librarian',
        store=True,
        help='Indicates if the user is a librarian.'
    )

    @api.depends('groups_id')
    def _compute_is_librarian(self):
        librarian_group = self.env.ref('library_management.group_library_librarian', raise_if_not_found=False)
        for user in self:
            user.is_librarian = bool(librarian_group and librarian_group in user.groups_id)