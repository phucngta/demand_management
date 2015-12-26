'''
Created on Dec 15, 2015

@author: Nguyen Phuc
'''
from datetime import datetime
from dateutil.relativedelta import relativedelta
from openerp import models, fields, api, exceptions

class Term(models.Model):
    _name = 'demand.term'
    _description = 'Demand term'
    name = fields.Char('Term Name', required=True)
    date_start= fields.Date('Start of Term', required=True, states={'done':[('readonly',True)]})
    date_end= fields.Date('End of Term', required=True, states={'done':[('readonly',True)]})
    num_cycle=fields.Integer('Number of Cycles')
    # tp = fields.Char()
    type_period=fields.Selection([('day','day(s)'),('week','week(s)'),('month','month(s)')],default='day')
    state = fields.Selection([('draft','Open'), ('done','Closed')], 'Status', readonly=True, copy=False, default='draft')
    period_ids = fields.One2many('demand.period', 'term_id', string= 'Periods')
    
    @api.one
    @api.constrains('date_start', 'date_end')
    def check_dates(self):
        if self.date_start >= self.date_end:
            raise exceptions.ValidationError("Ngay bat dau phai nho hon ngay ket thuc")
            
    @api.multi
    def action_draft(self):
        self.state = 'draft'

    @api.multi
    def action_done(self):
        self.state = 'done'
    
    @api.one
    @api.depends('type_period','num_cycle')
    def create_period(self):
        period_obj = self.env['demand.period']        
        ds = datetime.strptime(self.date_start, '%Y-%m-%d')
        
        if self.type_period == 'month':
            while ds.strftime('%Y-%m-%d') < self.date_end:
                    de = ds + relativedelta(months = self.num_cycle, days=-1)
    
                    if de.strftime('%Y-%m-%d') > self.date_end:
                        de = datetime.strptime(self.date_end, '%Y-%m-%d')
    
                    period_obj.create({
                        'name': ds.strftime('%m/%Y'),
                        'date_start': ds.strftime('%Y-%m-%d'),
                        'date_end': de.strftime('%Y-%m-%d'),
                        'term_id': self.id,
                    })
                    ds = ds + relativedelta(months = self.num_cycle)
        
        elif self.type_period == 'week':
            while ds.strftime('%Y-%m-%d') < self.date_end:
                    de = ds + relativedelta(weeks = self.num_cycle, days=-1)
    
                    if de.strftime('%Y-%m-%d') > self.date_end:
                        de = datetime.strptime(self.date_end, '%Y-%m-%d')
    
                    period_obj.create({
                        'name': ds.strftime('Week %W %m/%Y'),
                        'date_start': ds.strftime('%Y-%m-%d'),
                        'date_end': de.strftime('%Y-%m-%d'),
                        'term_id': self.id,
                    })
                    ds = ds + relativedelta(weeks = self.num_cycle)
                    
        elif self.type_period == 'day':
            while ds.strftime('%Y-%m-%d') < self.date_end:
                    de = ds + relativedelta(days = self.num_cycle-1)
    
                    if de.strftime('%Y-%m-%d') > self.date_end:
                        de = datetime.strptime(self.date_end, '%Y-%m-%d')
    
                    period_obj.create({
                        'name': ds.strftime('Period %d')+de.strftime('-%d')+ds.strftime('/%m'),
                        'date_start': ds.strftime('%Y-%m-%d'),
                        'date_end': de.strftime('%Y-%m-%d'),
                        'term_id': self.id,
                    })
                    ds = ds + relativedelta(days = self.num_cycle)
        

class Period(models.Model):
    _name = 'demand.period'
    _description = 'Demand period'
    _order = 'date_start, id' 
    name = fields.Char('Period Name', required=True)
    date_start= fields.Date('Start of Period', required=True, states={'done':[('readonly',True)]})
    date_end= fields.Date('End of Period', required=True, states={'done':[('readonly',True)]})
    term_id = fields.Many2one('demand.term', string='Term Name', required=True, states={'done':[('readonly',True)]}, select=True)
    state = fields.Selection([('draft','Open'), ('done','Closed')], 'Status', readonly=True, copy=False, default='draft')

    @api.multi
    def action_draft(self):
        self.state = 'draft'

    @api.multi
    def action_done(self):
        self.state = 'done'

    @api.one
    @api.constrains('date_start', 'date_end')
    def check_dates(self):
        if self.date_start > self.date_end:
            raise exceptions.ValidationError("Ngay bat dau phai nho hon ngay ket thuc")
           
    