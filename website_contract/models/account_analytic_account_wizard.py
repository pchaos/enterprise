# -*- coding: utf-8 -*-
from openerp import models, fields, api


class account_analytic_account_wizard(models.TransientModel):
    _name = 'account.analytic.account.option.wizard'

    def _default_account(self):
        return self.env['account.analytic.account'].browse(self._context.get('active_id'))

    account_id = fields.Many2one('account.analytic.account', string="Contract", required=True, default=_default_account)
    option_lines = fields.One2many('account.analytic.transient.option', 'wizard_id', string="Options")

    @api.multi
    def create_sale_order(self):
        template_id = self.env['account.analytic.account'].browse(self.env.context.get('active_id')).template_id
        sale_order_obj = self.env['sale.order']
        order = sale_order_obj.create({
            'partner_id': self.account_id.partner_id.id,
            'project_id': self.account_id.id,
            'team_id': self.env['ir.model.data'].get_object_reference('website', 'salesteam_website_sales')[1],
            'pricelist_id': self.account_id.pricelist_id.id,
            })
        for line in self.option_lines:
            for option in template_id.option_invoice_line_ids:
                if line.product_id == option.product_id:
                    line.name = option.name
            self.account_id.partial_invoice_line(order, line)
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "views": [[False, "form"]],
            "res_id": order.id,
        }

    def _prepare_contract_lines(self):
        rec_lines = []
        for line in self.option_lines:
            rec_line = False
            for account_line in self.account_id.recurring_invoice_line_ids:
                if (line.product_id, line.uom_id) == (account_line.product_id, account_line.uom_id):
                    rec_line = (1, account_line.id, {'sold_quantity': account_line.sold_quantity + line.quantity})
            if not rec_line:
                rec_line = (0, 0, {'product_id': line.product_id.id,
                                   'name': line.name,
                                   'sold_quantity': line.quantity,
                                   'uom_id': line.uom_id.id,
                                   'price_unit': self.account_id.pricelist_id.with_context({'uom': line.uom_id.id}).price_get(line.product_id.id, 1)[self.account_id.pricelist_id.id]
                                   })
            rec_lines.append(rec_line)
        return rec_lines

    @api.multi
    def add_lines(self):
        rec_lines = self._prepare_contract_lines()
        self.account_id.write({'recurring_invoice_line_ids': rec_lines})


class account_analytic_transient_option(models.TransientModel):
    _name = "account.analytic.transient.option"
    _inherit = "account.analytic.invoice.line.option"

    def _product_domain(self):
        template_id = self.env['account.analytic.account'].browse(self.env.context.get('active_id')).template_id
        return [('id', 'in', [option.product_id.id for option in template_id.option_invoice_line_ids] + [line.product_id.id for line in template_id.recurring_invoice_line_ids])]

    wizard_id = fields.Many2one('account.analytic.account.option.wizard')
    product_id = fields.Many2one('product.product', domain=_product_domain)
    quantity = fields.Float(inverse='_inverse_quantity')

    def _inverse_quantity(self):
        for line in self:
            line.sold_quantity = line.quantity