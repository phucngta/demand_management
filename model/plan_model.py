# -*- coding: utf-8 -*-
from openerp import models, fields, api

class planning(models.Model):
    _name = 'demand.planning'

    @api.one
    @api.depends('product_id')
    def _get_stock(self):
        if self.product_id:
            for op in self.product_id.orderpoint_ids:
                self.product_min_qty = op.product_min_qty
                self.product_max_qty = op.product_max_qty

            self.qty_available = self.product_id.qty_available
            self.virtual_available = self.product_id.virtual_available
            self.incoming_qty = self.product_id.incoming_qty
            self.outgoing_qty = self.product_id.outgoing_qty

    name = fields.Char('Planning Name', required=True)

    forecast_id = fields.Many2one('demand.forecast', string = 'Reference', required=True, domain=[('state','=','open')], readonly=True)
    forecast_lines = fields.One2many('demand.forecast.line', 'planning_id',string = 'Forecast Lines', readonly=True)
    planning_lines = fields.One2many('demand.planning.line', 'planning_id',string = 'Planning Lines', readonly=True, states={'draft': [('readonly',False)]})
    
    term_id= fields.Many2one('demand.term', string='Term', readonly=True)

    product_id = fields.Many2one('product.product',string="Product", readonly=True)
    product_uom = fields.Many2one('product.uom', string='Unit of Measure', readonly=True)

    qty_available = fields.Float('Stock On Hand', readonly=True, compute=_get_stock)
    virtual_available = fields.Float('Stock Accounting', readonly=True, compute=_get_stock)
    incoming_qty = fields.Float('Incoming Quantity', readonly=True, compute=_get_stock)
    outgoing_qty = fields.Float('Outging Quantity', readonly=True, compute=_get_stock)

    warehouse_id = fields.Many2one('stock.warehouse', required=True, string="Warehouse", readonly=True, states={'draft': [('readonly',False)]})
    product_min_qty = fields.Float('Minimum Stock Rule', readonly=True, compute=_get_stock)
    product_max_qty = fields.Float('Maximum Stock Rule', readonly=True, compute=_get_stock)

    state = fields.Selection([
            ('draft', "Draft"),
            ('open', "Open"),
            ('close', "Close"),
            ], default='draft')
    @api.multi
    def action_draft(self):
        self.state = 'draft'

    @api.multi
    def action_open(self):
        self.state = 'open'

    @api.multi
    def action_close(self):
        self.state = 'close'
        self.forecast_id.state  = 'done'
        for line in self.forecast_lines:
            line.state = 'done'
        for line in self.planning_lines:
            line.state = 'close'


class PlanningLine(models.Model):
    _name = 'demand.planning.line'

    @api.one
    @api.depends('forecast_qty','virtual_available','product_min_qty')
    def _calculate_consult_quantity(self):
        consult_quantity = self.forecast_qty - self.virtual_available + self.product_min_qty
        if consult_quantity > 0:
            self.consult_qty = consult_quantity
        else: 
            self.consult_qty = 0   

    name = fields.Char('Planning Line Name', required=True)

    forecast_line_id = fields.Many2one('demand.forecast.line', string='Reference', required=True, readonly=True)
    planning_id = fields.Many2one('demand.planning', string='Source', required=True, readonly=True)
    procurement_id = fields.Many2one('procurement.order', string="Procurement", readonly=True)

    term_id= fields.Many2one('demand.term', string='Term', required=True, readonly=True)
    period_id = fields.Many2one('demand.period', string='Period', required=True, readonly=True)

    demand_qty = fields.Float('Demand Quantity', readonly=True)
    forecast_qty = fields.Float('Forecast Quantity', readonly=True)

    qty_available = fields.Float('Stock On Hand', readonly=True)
    virtual_available = fields.Float('Stock Accounting', readonly=True)
    incoming_qty = fields.Float('Incoming Quantity', readonly=True)
    outgoing_qty = fields.Float('Outging Quantity', readonly=True)

    product_min_qty = fields.Float('Minimum Quantity', readonly=True)
    product_max_qty = fields.Float('Maximum Quantity', readonly=True)

    consult_qty = fields.Float('Consultant Quantity', readonly=True, compute=_calculate_consult_quantity)
    plan_qty = fields.Float('Procurement Quantity', required=True, default=0 ,readonly=True, states={'draft': [('readonly',False)]})

    state = fields.Selection([
            ('draft', "Draft"),
            ('open', "Open"),
            ('close', "Close"),
            ], default='draft')

    @api.multi
    def action_draft(self):
        self.state = 'draft'

    @api.multi
    def action_open(self):
        self.state = 'open'

    @api.multi
    def action_close(self):
        self.state = 'close'

    # @api.multi
    # def request_procurement(self):
    #     value_dict = {'product_id': self.planning_id.product_id.id,
    #                   'uom_id': self.planning_id.product_id.uom_id.id,
    #                   'date_planned': self.period_id.date_start,
    #                   'qty': self.plan_qty,
    #                   }
    #     res_id = self.env['make.procurement'].create(value_dict)
    #     self.state = 'open'

    #     return {'view_type': 'form',
    #             'view_mode': 'form',
    #             'res_model': 'make.procurement',
    #             'res_id': res_id.id,
    #             'view_id': False,
    #             'type': 'ir.actions.act_window',
    #             'target': 'new',
    #             }
    
    @api.multi
    def create_procurement(self):
        procurement_obj = self.env['procurement.order']
        # procure_lst = []
        # for record in self:
        #     for product_line in record.forecast_lines:
        if not self.procurement_id.exists():
            res_id = procurement_obj.create({
                    'name': 'Procurement ' +self.period_id.name+ '('+self.term_id.name+')',
                    'date_planned': self.period_id.date_start,
                    'product_id': self.planning_id.product_id.id,
                    'product_uom': self.planning_id.product_id.uom_id.id,
                    'product_qty': self.plan_qty,
                    'warehouse_id': self.planning_id.warehouse_id.id,
                    'location_id': self.planning_id.warehouse_id.lot_stock_id.id,
                    'company_id': self.planning_id.warehouse_id.company_id.id,
                    'origin': self.name,
                    })
            self.procurement_id = res_id.id
            self.state = 'open'        

    @api.multi
    def show_procurement(self):
        return {
            'view_mode': 'form',
            'res_model': 'procurement.order',
            'res_id': self.procurement_id.id,
            'view_id': False,
            'type': 'ir.actions.act_window',
            }