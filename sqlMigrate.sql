
ALTER TABLE `t_contract` ADD COLUMN `sale_person` varchar(20) COMMENT '客户经理' AFTER `shop`;

ALTER TABLE `t_commit_info` ADD COLUMN `pay_amt` int(20) NOT NULL DEFAULT '0' COMMENT '实际支付额' AFTER `applyer`;

ALTER TABLE `t_contract_repay` CHANGE COLUMN `deadline` `deadline` date NOT NULL COMMENT '应还日期';

ALTER TABLE `t_contract` CHANGE COLUMN `loan_date` `loan_date` date DEFAULT NULL COMMENT '放款日期';

ALTER TABLE `t_contract` ADD COLUMN `delay_day` int NOT NULL DEFAULT '0' COMMENT '最长逾期天数' AFTER `repay_date`;

ALTER TABLE `t_repayment` ADD COLUMN `shop` varchar(20) COMMENT '所在门店' AFTER `refund_time`;

--20180418--
update t_contract set delayed_day=null;
ALTER TABLE `t_contract` CHANGE COLUMN `delayed_day` `repay_date` date DEFAULT NULL COMMENT '最近还款日',
ADD COLUMN `updated_time` timestamp NOT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日期' AFTER `file_id`,
 CHANGE COLUMN `create_time` `created_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建日期' AFTER `updated_time`;



ALTER TABLE `t_commit_refund`
MODIFY COLUMN `deadline`  datetime NULL COMMENT '截止日期' AFTER `amount`;

/*协商表修改 20180411*/
ALTER TABLE `t_commit_refund`
DROP COLUMN `is_settled`,
MODIFY COLUMN `remark`  varchar(0) CHARACTER SET utf8 COLLATE utf8_general_ci NULL DEFAULT NULL COMMENT '协商备注' AFTER `type`,
MODIFY COLUMN `result`  int(3) NULL DEFAULT 0 COMMENT '审批结果（0、待审核；100、通过；200、拒绝）' AFTER `approve_remark`,
MODIFY COLUMN `is_valid`  int(2) UNSIGNED NULL DEFAULT 0 COMMENT '是否有效(0、有效；-1；无效)' AFTER `result`,
ADD COLUMN `discount_type`  int(2) NULL COMMENT '减免类型:0逾期结清；1全部结清' AFTER `type`;



/*计划表修改 20180411*/
ALTER TABLE `t_refund_plan` ADD COLUMN `amt` INT (20) NOT NULL DEFAULT '0' COMMENT '应还金额' AFTER `tensor`,
 CHANGE COLUMN `principal` `principal` INT (20) NOT NULL DEFAULT '0' COMMENT '应还本金（单位：分/人民币）' AFTER `amt`,
 CHANGE COLUMN `interest` `interest` INT (20) UNSIGNED ZEROFILL NOT NULL DEFAULT '0' COMMENT '应还利息(单位：分/人民币)' AFTER `principal`,
 CHANGE COLUMN `delay_day` `delay_day` INT (11) NOT NULL DEFAULT '0' COMMENT '逾期天数' AFTER `interest`,
 CHANGE COLUMN `fee` `fee` INT (11) NOT NULL DEFAULT '0' COMMENT '滞纳金（分）' AFTER `delay_day`,
 ADD COLUMN `actual_amt` INT (20) NOT NULL DEFAULT '0' COMMENT '实还本息' AFTER `fee`,
 ADD COLUMN `actual_fee` INT (20) NOT NULL DEFAULT '0' COMMENT '实还滞纳金' AFTER `actual_amt`;

/*合同表状态修改 20180410*/
ALTER TABLE `t_contract`
MODIFY COLUMN `is_settled`  int(20) NOT NULL DEFAULT 0 COMMENT '合同状态是否(0、还款中；100、逾期；200、移交外催；300、结清)' AFTER `refund_sum`,
MODIFY COLUMN `is_dealt`  int(2) NULL DEFAULT NULL COMMENT '当天任务是否处理(1为已处理，0为未处理)' AFTER `is_settled`;


ALTER TABLE `t_refund_plan` ADD COLUMN `fee` int NOT NULL DEFAULT '0' COMMENT '滞纳金（分）' AFTER `interest`;
ALTER TABLE `t_refund_plan` ADD COLUMN `delay_day` int NOT NULL DEFAULT '0' COMMENT '逾期天数' AFTER `interest`;
ALTER TABLE `t_contract` ADD COLUMN `mobile_no` varchar(20) NOT NULL DEFAULT '' COMMENT '联系电话' AFTER `customer`;

