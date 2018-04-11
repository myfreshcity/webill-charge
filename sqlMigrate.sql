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

