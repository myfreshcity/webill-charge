ALTER TABLE `t_refund_plan` ADD COLUMN `fee` int NOT NULL DEFAULT '0' COMMENT '滞纳金（分）' AFTER `interest`;
ALTER TABLE `t_refund_plan` ADD COLUMN `delay_day` int NOT NULL DEFAULT '0' COMMENT '逾期天数' AFTER `interest`;
ALTER TABLE `t_contract` ADD COLUMN `mobile_no` varchar(20) NOT NULL DEFAULT '' COMMENT '联系电话' AFTER `customer`;