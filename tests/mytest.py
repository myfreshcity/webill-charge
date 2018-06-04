import datetime
import unittest

from app import create_app
from app.main.db_service import recount_fee, get_latest_repay_date
from app.main.match_engine import MatchEngine
from app.models import Repayment, Contract, ContractRepay, CommitInfo


class MyTest(unittest.TestCase):  # 继承unittest.TestCase
    def tearDown(self):
        # 每个测试用例执行之后做操作
        print('111')

    def setUp(self):
        self.contract = Contract.query.filter(Contract.id == '25').one()
        self.contract.shop = '上海门店'
        self.contract.contract_amount = 10000
        self.contract.tensor = 4
        self.contract.repay_type = 0
        self.contract.prepay_type = 0 #提前还款不计算利息
        self.contract.is_settled = 100 # 重置合同为逾期

        self.plan = ContractRepay.query.filter(ContractRepay.id == '49').first()
        self.plan2 = ContractRepay.query.filter(ContractRepay.id == '50').first()
        self.plan3 = ContractRepay.query.filter(ContractRepay.id == '51').first()
        self.plan4 = ContractRepay.query.filter(ContractRepay.id == '52').first()

        self.comInfo = CommitInfo.query.filter(CommitInfo.id == '21').first()
        self.comInfo.remain_amt = 0

        self.refund = Repayment.query.filter(Repayment.id == '103').first()
        self.refund.contract_id = None
        self.refund.t_status = 2
        self.refund.shop = '上海门店'


    @classmethod
    def tearDownClass(self):
        # 必须使用 @ classmethod装饰器, 所有test运行完后运行一次
        print('4444444')

    @classmethod
    def setUpClass(self):
        # 必须使用@classmethod 装饰器,所有test运行前运行一次
        app = create_app()
        app.log_format = '%(asctime)s %(funcName)s [%(levelname)s] %(message)s'
        app.debug = True
        ctx = app.app_context()
        ctx.push()

    def init_repay_plan(self,plan, deadline):
        plan.deadline = deadline
        plan.delay_day = 0
        plan.amt = 5000
        plan.fee = 0
        recount_fee(plan, self.contract)
        plan.actual_amt = 0
        plan.actual_fee = 0
        plan.is_settled = 0
        plan.settled_date = None

    def init_repayment(self,amount,refund_time):
        self.refund.amount = amount*100
        self.refund.remain_amt = self.refund.amount
        self.refund.refund_time = refund_time

    # 正常还款
    def test_001(self):
        self.init_repay_plan(self.plan, datetime.date.today())
        self.init_repay_plan(self.plan2, datetime.date.today() + datetime.timedelta(days=2))
        self.init_repay_plan(self.plan3, datetime.date.today() + datetime.timedelta(days=4))
        self.init_repay_plan(self.plan4, datetime.date.today() + datetime.timedelta(days=8))
        self.contract.repay_date = get_latest_repay_date(self.contract.id)

        self.init_repayment(50, datetime.datetime.now())
        result = MatchEngine().match_by_refund(self.refund)

        self.assertEqual(result, None)
        self.assertEqual(self.contract.is_settled, 0)


    # 提前还款
    def test_002(self):
        self.init_repay_plan(self.plan, datetime.date.today() + datetime.timedelta(days=1))
        self.init_repay_plan(self.plan2, datetime.date.today() + datetime.timedelta(days=2))
        self.init_repay_plan(self.plan3, datetime.date.today() + datetime.timedelta(days=4))
        self.init_repay_plan(self.plan4, datetime.date.today() + datetime.timedelta(days=8))
        self.contract.repay_date = get_latest_repay_date(self.contract.id)

        self.init_repayment(51, datetime.datetime.now())
        result = MatchEngine().match_by_refund(self.refund)
        self.assertEqual(result, None)
        self.assertEqual(self.contract.is_settled, 0)
        self.assertEqual(self.refund.remain_amt, 100)

    # 结清还款
    def test_003(self):
        self.init_repay_plan(self.plan, datetime.date.today() - datetime.timedelta(days=2))
        self.init_repay_plan(self.plan2, datetime.date.today() - datetime.timedelta(days=1))
        self.init_repay_plan(self.plan3, datetime.date.today() + datetime.timedelta(days=4))
        self.init_repay_plan(self.plan4, datetime.date.today() + datetime.timedelta(days=8))
        self.contract.repay_date = get_latest_repay_date(self.contract.id)

        self.comInfo.remain_amt = 65*100
        self.comInfo.discount_type = 1
        self.comInfo.apply_date = datetime.datetime.now()

        self.init_repayment(710, datetime.datetime.now())
        result = MatchEngine().match_by_refund(self.refund)
        self.assertEqual(result, None)
        self.assertEqual(self.contract.is_settled, 300)

    # 清除欠款
    def test_004(self):
        self.init_repay_plan(self.plan, datetime.date.today() - datetime.timedelta(days=2))
        self.init_repay_plan(self.plan2, datetime.date.today() - datetime.timedelta(days=1))
        self.init_repay_plan(self.plan3, datetime.date.today() + datetime.timedelta(days=4))
        self.init_repay_plan(self.plan4, datetime.date.today() + datetime.timedelta(days=8))
        self.contract.repay_date = get_latest_repay_date(self.contract.id)

        self.comInfo.remain_amt = 100*100
        self.comInfo.discount_type = 0
        self.comInfo.apply_date = datetime.datetime.now()

        self.init_repayment(600, datetime.datetime.now())
        result = MatchEngine().match_by_refund(self.refund)
        self.assertEqual(result, None)
        self.assertEqual(self.contract.is_settled, 0)

    # 多期清除欠款
    def test_005(self):
        self.assertEqual(2, 2)

    # 指定流水冲账(部分额度)
    def test_0060(self):
        self.init_repay_plan(self.plan, datetime.date.today() - datetime.timedelta(days=2))
        self.init_repay_plan(self.plan2, datetime.date.today() - datetime.timedelta(days=1))
        self.init_repay_plan(self.plan3, datetime.date.today() + datetime.timedelta(days=4))
        self.init_repay_plan(self.plan4, datetime.date.today() + datetime.timedelta(days=8))
        self.contract.repay_date = get_latest_repay_date(self.contract.id)

        self.init_repayment(500, datetime.datetime.now())
        result = MatchEngine().match_by_contract(self.contract, self.refund,False,150*100)
        self.assertEqual(result, None)
        self.assertEqual(self.plan.actual_amt, 50 * 100)
        self.assertEqual(self.plan2.actual_amt, 50 * 100)
        self.assertEqual(self.refund.remain_amt, 350*100)

    # 指定流水冲账(滞纳金优先)
    def test_0061(self):
        self.init_repay_plan(self.plan, datetime.date.today() - datetime.timedelta(days=2))
        self.init_repay_plan(self.plan2, datetime.date.today() - datetime.timedelta(days=1))
        self.init_repay_plan(self.plan3, datetime.date.today() + datetime.timedelta(days=4))
        self.init_repay_plan(self.plan4, datetime.date.today() + datetime.timedelta(days=8))
        self.contract.repay_date = get_latest_repay_date(self.contract.id)

        self.init_repayment(500, datetime.datetime.now())
        result = MatchEngine().match_by_contract(self.contract, self.refund, True, 150 * 100)
        self.assertEqual(result, None)
        self.assertEqual(self.plan.actual_amt, 50 * 100)
        self.assertEqual(self.plan2.actual_amt, 0)
        self.assertEqual(self.refund.remain_amt, 350 * 100)

    # 指定流水冲账(提前还款部分冲账)
    def test_0062(self):
        self.init_repay_plan(self.plan, datetime.date.today() + datetime.timedelta(days=1))
        self.init_repay_plan(self.plan2, datetime.date.today() + datetime.timedelta(days=2))
        self.init_repay_plan(self.plan3, datetime.date.today() + datetime.timedelta(days=4))
        self.init_repay_plan(self.plan4, datetime.date.today() + datetime.timedelta(days=8))
        self.contract.repay_date = get_latest_repay_date(self.contract.id)

        self.init_repayment(500, datetime.datetime.now())
        result = MatchEngine().match_by_contract(self.contract, self.refund, True, 100 * 100,True)
        self.assertEqual(result, None)
        self.assertEqual(self.refund.remain_amt, 400 * 100)


    # 还款后减免
    def test_0070(self):
        self.init_repay_plan(self.plan, datetime.date.today() - datetime.timedelta(days=2))
        self.init_repay_plan(self.plan2, datetime.date.today() - datetime.timedelta(days=1))
        self.init_repay_plan(self.plan3, datetime.date.today() + datetime.timedelta(days=4))
        self.init_repay_plan(self.plan4, datetime.date.today() + datetime.timedelta(days=8))
        self.contract.repay_date = get_latest_repay_date(self.contract.id)

        self.init_repayment(600, datetime.datetime.now())
        MatchEngine().match_by_refund(self.refund)

        self.comInfo.remain_amt = 175 * 100
        self.comInfo.discount_type = 1
        self.comInfo.apply_date = datetime.datetime.now()
        result = MatchEngine().match_by_contract(self.contract)

        self.assertEqual(result, None)
        self.assertEqual(self.contract.is_settled, 300)

    # 提前还款分次结清
    def test_0071(self):
        self.init_repay_plan(self.plan, datetime.date.today() + datetime.timedelta(days=1))
        self.init_repay_plan(self.plan2, datetime.date.today() + datetime.timedelta(days=2))
        self.init_repay_plan(self.plan3, datetime.date.today() + datetime.timedelta(days=4))
        self.init_repay_plan(self.plan4, datetime.date.today() + datetime.timedelta(days=8))
        self.contract.repay_date = get_latest_repay_date(self.contract.id)

        self.init_repayment(51, datetime.datetime.now())
        MatchEngine().match_by_refund(self.refund)
        self.assertEqual(self.refund.remain_amt, 1*100)

        MatchEngine().match_by_contract(self.contract, self.refund, True, 1 * 100, True)
        self.assertEqual(self.refund.remain_amt, 0 * 100)

        self.init_repayment(76, datetime.datetime.now())
        MatchEngine().match_by_contract(self.contract, self.refund, True, 76 * 100, True)


        self.comInfo.remain_amt = 0 * 100
        self.comInfo.discount_type = 1
        self.comInfo.apply_date = datetime.datetime.now() + datetime.timedelta(days=8)
        result = MatchEngine().match_by_contract(self.contract)

        self.assertEqual(result, None)
        self.assertEqual(self.contract.is_settled, 300)

    # 提前还款一次结清
    def test_0072(self):
        self.init_repay_plan(self.plan, datetime.date.today() + datetime.timedelta(days=1))
        self.init_repay_plan(self.plan2, datetime.date.today() + datetime.timedelta(days=2))
        self.init_repay_plan(self.plan3, datetime.date.today() + datetime.timedelta(days=4))
        self.init_repay_plan(self.plan4, datetime.date.today() + datetime.timedelta(days=8))
        self.contract.repay_date = get_latest_repay_date(self.contract.id)

        self.init_repayment(125, datetime.datetime.now())
        MatchEngine().match_by_refund(self.refund)

        MatchEngine().match_by_contract(self.contract, self.refund, True, 25 * 100, True)

        # 补一个期后减免
        self.comInfo.remain_amt = 0 * 100
        self.comInfo.discount_type = 1
        self.comInfo.apply_date = datetime.datetime.now()+ datetime.timedelta(days=8)
        result = MatchEngine().match_by_contract(self.contract)

        self.assertEqual(result, None)
        self.assertEqual(self.refund.remain_amt, 0*100)
        self.assertEqual(self.contract.is_settled, 300)


    # 期后减免结清
    def test_0073(self):
        self.init_repay_plan(self.plan, datetime.date.today() + datetime.timedelta(days=1))
        self.init_repay_plan(self.plan2, datetime.date.today() + datetime.timedelta(days=2))
        self.init_repay_plan(self.plan3, datetime.date.today() + datetime.timedelta(days=4))
        self.init_repay_plan(self.plan4, datetime.date.today() + datetime.timedelta(days=8))
        self.contract.repay_date = get_latest_repay_date(self.contract.id)

        self.init_repayment(120, datetime.datetime.now())
        MatchEngine().match_by_refund(self.refund)
        self.assertEqual(self.refund.remain_amt, 20*100)

        MatchEngine().match_by_contract(self.contract, self.refund, True, 20 * 100, True)

        self.comInfo.remain_amt = 5 * 100
        self.comInfo.discount_type = 1
        self.comInfo.apply_date = datetime.datetime.now()
        result = MatchEngine().match_by_contract(self.contract)

        self.assertEqual(result, None)
        self.assertEqual(self.contract.is_settled, 300)



if __name__ == '__main__':
    unittest.main()  # 运行所有的测试用例