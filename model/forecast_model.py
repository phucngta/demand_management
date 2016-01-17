'''
Created on Dec 15, 2015

@author: Nguyen Phuc
'''
from datetime import datetime
from openerp import models, fields, api

class forecast(models.Model):
    _name = 'demand.forecast'

    @api.one
    @api.depends('forecast_lines')
    def _count_forecast_lines(self):
        forecast_line_lst = []
        sum_demand = 0
        for line in self.forecast_lines:
            if line.id:
                forecast_line_lst.append(line.id)
                sum_demand += line.demand
        
        forecast_line_count = len(forecast_line_lst)
        if forecast_line_count > 0:
            self.avg_demand = sum_demand /forecast_line_count

    # @api.multi
    # def _generate_name_forecast(self):
    #     forecast_obj = self.env['demand.forecast']
    #     generate_id = 0
    #     for line in forecast_obj.browse([]):
    #         if line.id:
    #             generate_id = line.id + 1

    #     return "FC0"+ str(generate_id)

    name = fields.Char('Forecast Name', required=True)
    term_id= fields.Many2one('demand.term', string='Term', required=True, readonly=True, states={'draft': [('readonly',False)]})
    period_id = fields.Many2one('demand.period', string=' End Period', required=True, readonly=True, states={'draft': [('readonly',False)]})

    product_id = fields.Many2one('product.product',string="Product", required=True, readonly=True, states={'draft': [('readonly',False)]})
    product_uom = fields.Many2one('product.uom', string='Unit of Measure', required=True, readonly=True, states={'draft': [('readonly',False)]})
    forecast_lines = fields.One2many('demand.forecast.line', 'forecast_id', string='Forecast Line', readonly=True, states={'draft': [('readonly',False)]})

    forecast_method = fields.Selection([('sma','Simple Moving Average'),('es','Exponential Smoothing')], "Method" ,default='sma', readonly=True, states={'draft': [('readonly',False)]})
    interval = fields.Integer('Interval', required = True, default=2, readonly=True, states={'draft': [('readonly',False)]})
    alpha = fields.Float('Alpha', required = True, default=0.5, readonly=True, states={'draft': [('readonly',False)]})
    
    avg_demand = fields.Float(string='Average Demand', readonly=True, compute=_count_forecast_lines, store=True)

    mad = fields.Float(string='MAD', readonly=True)
    mape = fields.Float(string='MAPE', readonly=True)
    track_signal = fields.Float(string='Tracking Signal', readonly=True)

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
            self.mad = self.mape = self.track_signal = 0

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
        forecast_line_obj = self.env['demand.forecast.line']
        ids = self.forecast_lines.mapped('id')
        number_lines = len(ids)

        # Gan forecast dau tien
        first_forecast_line = forecast_line_obj.browse([ids[0]])
        forecast_value = first_forecast_line.demand
        first_forecast_line.write({'forecast': forecast_value})

        # Tinh forecast trong tung sale history
        sum_error = sum_ab_error = error = 0
        i = 1
        while i < number_lines :
            forecast_value = forecast_value + alpha*error

            forecast_line = forecast_line_obj.browse([ids[i]])
            forecast_line.write({'forecast': forecast_value})

            error = forecast_line.demand - forecast_value
            sum_error += error
            sum_ab_error += abs(error)
            i += 1

        # Tinh do sai lech
        self.mad = sum_ab_error/number_lines
        self.mape = self.mad/self.avg_demand
        self.track_signal = sum_error/self.mad

    @api.one
    @api.depends('interval')
    def _forecast_by_simple_moving_average(self, interval):
        # Lay so phan tu lich su
        forecast_line_obj = self.env['demand.forecast.line']
        ids = self.forecast_lines.mapped('id')
        number_lines = len(ids)
        
        # Kiem tra interval co lon hon so luong lich su
        if number_lines < interval:
            return False

        # Tinh gia tri forecast
        sum_error = sum_ab_error = error = 0
        i = 0
        while  i < number_lines:
            # Gan forecast dau tien
            if i < interval:
                forecast_line_obj.browse([ids[i]]).write({'forecast': 0})

            else:
                count_down = interval
                sum_demand_interval = 0
                index = i - 1

                while count_down > 0:
                    sum_demand_interval += forecast_line_obj.browse([ids[index]]).demand
                    index -= 1
                    count_down -= 1

                forecast_value = sum_demand_interval/interval
                forecast_line_obj.browse([ids[i]]).write({'forecast': forecast_value})

                error = forecast_line_obj.browse([ids[i]]).demand - forecast_value
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
    def create_forecast_lines(self):
        # Xoa history cu
        self.forecast_lines.unlink()

        # Tao Temporate Demand
        forecast_obj = self.env['demand.forecast']
        if forecast_obj.search([('name','=','Demand '+self.name)]).exists():
            tmp_demand = forecast_obj.search([('name','=','Demand '+self.name)])
            tmp_demand.forecast_lines.unlink()
        else: 
            tmp_demand = forecast_obj.create({
                'name' : 'Demand '+self.name,
                'term_id' : self.term_id.id,
                'period_id' : self.period_id.id,
                'product_id' : self.product_id.id,
                'product_uom' : self.product_uom.id,
                'state' : 'done',
            })

        # Tao lich su
        forecast_line_obj = self.env['demand.forecast.line']
        de = datetime.strptime(self.period_id.date_end, '%Y-%m-%d')
        for pe in self.term_id.period_ids:
            if pe.date_end <= de.strftime('%Y-%m-%d'):
                forecast_line_obj.create({
                    'name' : 'FC '+pe.name,
                    'period_id' : pe.id,
                    'term_id' : self.term_id.id,
                    'forecast_id' : self.id,
                    'demand' : self._sale_per_product(pe),
                })
                forecast_line_obj.create({
                    'name' : 'DM '+pe.name,
                    'period_id' : pe.id,
                    'term_id' : self.term_id.id,
                    'forecast_id' : tmp_demand.id,
                    'forecast' : self._sale_per_product(pe),
                    'state' : 'done',
                })

    @api.multi
    def show_graph_forecast(self):
        forecast_line_lst = []

        forecast_obj = self.env['demand.forecast']
        tmp_demand = forecast_obj.search([('name','=','Demand '+self.name)])
        if tmp_demand:
            for line in tmp_demand.forecast_lines:
                if line.id:
                    forecast_line_lst.append(line.id)

        for line in self.forecast_lines:
            if line.id:
                forecast_line_lst.append(line.id)

        return {
            'view_mode': 'graph',
            'res_model': 'demand.forecast.line',
            'res_ids': forecast_line_lst,
            'domain': [('id', 'in', forecast_line_lst)],
            'type': 'ir.actions.act_window',
            'target': 'new',
            }

class forecastLine (models.Model):
    _name = 'demand.forecast.line'

    name = fields.Char('Forecast Line Name', required=True)
    forecast_id = fields.Many2one('demand.forecast', string='Source', readonly=True)

    term_id = fields.Many2one('demand.term', string='Term', store=True, related="forecast_id.term_id", readonly=True)
    period_id= fields.Many2one('demand.period', string='Period', store=True, domain = "[('period_id.id','in','term_id.period_ids.mapped('id')')]", required=True)

    demand = fields.Float('Demand')
    forecast = fields.Float('Forecast')

    state = fields.Selection([('draft','Open'), ('done','Closed')], 'Status', readonly=True, default='draft')

    @api.multi
    def action_draft(self):
        self.state = 'draft'

    @api.multi
    def action_done(self):
        self.state = 'done'