'''
Created on Dec 15, 2015

@author: Nguyen Phuc
'''
from datetime import datetime
from openerp import models, fields, api

class forecast(models.Model):
    _name = 'demand.forecast'
    _description = 'Forecast Demand'

    @api.one
    @api.depends('history_ids')
    def _count_history(self):
        history_lst = []
        sum_demand = 0
        for line in self.history_ids:
            if line.id:
                history_lst.append(line.id)
                sum_demand += line.demand
        
        history_count = len(history_lst)
        if history_count > 0:
            self.avg_demand = sum_demand /history_count

    name = fields.Char('Forecast Name', required=True)
    term_id= fields.Many2one('demand.term', string='Term', required=True, readonly=True, states={'draft': [('readonly',False)]})
    period_id = fields.Many2one('demand.period', string='Period', required=True, readonly=True, states={'draft': [('readonly',False)]})

    product_id = fields.Many2one('product.product',string="Product", required=True, readonly=True, states={'draft': [('readonly',False)]})
    product_uom = fields.Many2one('product.uom', string='Unit of Measure', required=True, readonly=True, states={'draft': [('readonly',False)]})
    history_ids = fields.One2many('demand.history', 'forecast_id', string='Sale History', readonly=True, states={'draft': [('readonly',False)]})
    # history_count = fields.Integer(compute=_count_history, store=True)

    forecast_method = fields.Selection([('sma','Simple Moving Average'),('es','Exponential Smoothing')], "Method" ,default='sma', readonly=True, states={'draft': [('readonly',False)]})
    interval = fields.Integer('Interval', required = True, default=2, readonly=True, states={'draft': [('readonly',False)]})
    alpha = fields.Float('Alpha', required = True, default=0.5, readonly=True, states={'draft': [('readonly',False)]})
    
    # sum_error = fields.Float(string='Sum error')
    avg_demand = fields.Float(string='Average Demand', readonly=True, compute=_count_history, store=True)

    mad = fields.Float(string='MAD', readonly=True)
    mape = fields.Float(string='MAPE', readonly=True)
    track_signal = fields.Float(string='Tracking Signal', readonly=True)
    forecast_quantity = fields.Float(string='Forecast Quantity', readonly=True)

    state = fields.Selection([
        ('draft', "Draft"),
        ('open', "Open"),
        ('done', "Done"),
    ], 'Status', default='draft')

    @api.multi
    def action_draft(self):
        self.state = 'draft'

    @api.multi
    def action_open(self):
        self.state = 'open'

    @api.multi
    def action_done(self):
        self.state = 'done'

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.product_uom = self.product_id.uom_id

    @api.onchange('forecast_method')
    def onchange_forecast_method(self):
        if self.forecast_method:
            self.forecast_quantity = self.mad = self.mape = self.track_signal = 0

    @api.onchange('term_id')
    def onchange_term_id(self):
        self.period_id = None
        res = {}
        if self.term_id:
            ids = self.term_id.period_ids.mapped('id')
            res['domain'] = {
            'period_id': [('id', 'in', ids)]
            }   
        return res

    @api.one
    @api.depends('alpha')
    def _forecast_by_exponentail_smoothing(self, alpha):
        # Lay so phan tu lich su
        history_obj = self.env['demand.history']
        ids = self.history_ids.mapped('id')
        number_lines = len(ids)

        # Gan forecast dau tien
        first_history = history_obj.browse([ids[0]])
        forecast_value = first_history.demand
        first_history.write({'forecast': forecast_value})

        # Tinh forecast trong tung sale history
        sum_error = sum_ab_error = error = 0
        i = 1
        while i < number_lines :
            forecast_value = forecast_value + alpha*error

            history_line = history_obj.browse([ids[i]])
            history_line.write({'forecast': forecast_value})

            error = history_line.demand - forecast_value
            sum_error += error
            sum_ab_error += abs(error)
            i += 1

        # Tinh du bao va do sai lech
        self.forecast_quantity = forecast_value + alpha*error
        self.mad = sum_ab_error/number_lines
        self.mape = self.mad/self.avg_demand
        self.track_signal = sum_error/self.mad

    @api.one
    @api.depends('interval')
    def _forecast_by_simple_moving_average(self, interval):
        # Lay so phan tu lich su
        history_obj = self.env['demand.history']
        ids = self.history_ids.mapped('id')
        number_lines = len(ids)
        
        # Kiem tra interval co lon hon so luong lich su
        if number_lines < interval:
            return False

        # Tinh forecast trong tung sale history
        sum_error = sum_ab_error = error = 0
        i = 0
        while  i <= number_lines:
            # Gan forecast dau tien
            if i < interval:
                history_obj.browse([ids[i]]).write({'forecast': 0})

            else:
                count_down = interval
                sum_demand_interval = 0
                index = i - 1

                while count_down > 0:
                    sum_demand_interval += history_obj.browse([ids[index]]).demand
                    index -= 1
                    count_down -= 1

                # Gan gia tri du bao cho sale history va forecast project
                if i == number_lines:
                    self.forecast_quantity = sum_demand_interval/interval
                else: 
                    forecast_value = sum_demand_interval/interval
                    history_obj.browse([ids[i]]).write({'forecast': forecast_value})

                    error = history_obj.browse([ids[i]]).demand - forecast_value
                    sum_error += error
                    sum_ab_error += abs(error)

            i += 1

        # Tinh sai lech
        self.mad = sum_ab_error/(number_lines - interval)
        self.mape = self.mad/self.avg_demand
        self.track_signal = sum_error/self.mad

    @api.multi
    @api.depends('forecast_method','interval', 'alpha')
    def run_forecast(self):
        if self.forecast_method == 'es':
            self._forecast_by_exponentail_smoothing(self.alpha)
        elif  self.forecast_method == 'sma':
            self._forecast_by_simple_moving_average(self.interval)

    @api.multi
    @api.depends('product_id')
    def _sale_per_product(self, pe):
        # so_obj = self.env['sale.order']
        sol_obj = self.env['sale.order.line']

        # Kiem tra cac don hang ve san pham co ton tai
        sol_with_product = sol_obj.search([('product_id','=',self.product_id.id), ('order_id.date_order','>=', pe.date_start), ('order_id.date_order','<=', pe.date_end)])
        if sol_with_product:
            sum_quantity = 0
            for sol in sol_with_product:
                sum_quantity += sol.product_uom_qty
            return sum_quantity

    @api.one
    @api.depends('period_id','term_id','product_id')
    def create_history(self):
        # Xoa history cu
        self.history_ids.unlink()

        # Tao Temporate Demand
        forecast_obj = self.env['demand.forecast']
        if forecast_obj.search([('name','=','Demand '+self.name)]).exists():
            tmp_demand = forecast_obj.search([('name','=','Demand '+self.name)])
            tmp_demand.history_ids.unlink()
        else: 
            tmp_demand = forecast_obj.create({
                'name' : 'Demand '+self.name,
                'term_id' : self.term_id.id,
                'period_id' : self.period_id.id,
                'product_id' : self.product_id.id,
                'product_uom' : self.product_uom.id,
            })

        # Tao lich su
        history_obj = self.env['demand.history']
        ds = datetime.strptime(self.period_id.date_start, '%Y-%m-%d')
        for pe in self.term_id.period_ids:
            if pe.date_end < ds.strftime('%Y-%m-%d'):
                history_obj.create({
                    'period_id' : pe.id,
                    'term_id' : self.term_id.id,
                    'forecast_id' : self.id,
                    'demand' : self._sale_per_product(pe),
                })
                history_obj.create({
                    'period_id' : pe.id,
                    'term_id' : self.term_id.id,
                    'forecast_id' : tmp_demand.id,
                    'forecast' : self._sale_per_product(pe),
                })

    @api.multi
    def show_graph_forecast(self):
        history_list = []

        forecast_obj = self.env['demand.forecast']
        tmp_demand = forecast_obj.search([('name','=','Demand '+self.name)])
        if tmp_demand:
            for line in tmp_demand.history_ids:
                if line.id:
                    history_list.append(line.id)

        for line in self.history_ids:
            if line.id:
                history_list.append(line.id)

        return {
            'view_mode': 'graph',
            'res_model': 'demand.history',
            'res_ids': history_list,
            'domain': [('id', 'in', history_list)],
            'type': 'ir.actions.act_window',
            'target': 'new',
            }

class history (models.Model):
    _name = 'demand.history'
    _description = 'Sale History'

    # @api.one
    # @api.depends('demand', 'forecast')
    # def _get_error(self):
    #     self.error = self.demand - self.forecast
    #     self.absolute_error = abs(self.demand - self.forecast)

    forecast_id = fields.Many2one('demand.forecast', string='Source', readonly=True)

    term_id = fields.Many2one('demand.term', string='Term', store=True, related="forecast_id.term_id", readonly=True)
    period_id= fields.Many2one('demand.period', string='Period', store=True, domain = "[('period_id.id','in','term_id.period_ids.mapped('id')')]", required=True)

    demand = fields.Float('Demand')
    forecast = fields.Float('Forecast')
    # error = fields.Float('Error', readonly=True, compute='_get_error', store=True)
    # absolute_error = fields.Float('Absolute Error', readonly=True, compute='_get_error', store=True)

    state = fields.Selection([('draft','Open'), ('done','Closed')], 'Status', readonly=True, default='draft')

    @api.multi
    def action_draft(self):
        self.state = 'draft'

    @api.multi
    def action_done(self):
        self.state = 'done'