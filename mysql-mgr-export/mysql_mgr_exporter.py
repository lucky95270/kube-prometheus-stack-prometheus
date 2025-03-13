import os
import time
import pymysql
import logging
import traceback
from prometheus_client import start_http_server, Gauge, Histogram

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# 读取 MySQL 配置，支持通过环境变量修改
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "user": os.getenv("MYSQL_USER", "monitor"),
    "password": os.getenv("MYSQL_PASSWORD", "password"),
    "database": os.getenv("MYSQL_DATABASE", "performance_schema"),
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}

# 定义 Prometheus 监控指标
MGR_MEMBER_COUNT = Gauge("mysql_mgr_member_count", "MySQL MGR 集群成员数量")
MGR_MEMBER_STATUS = Gauge("mysql_mgr_member_status", "MySQL MGR 节点状态 (1=ONLINE, 0=OFFLINE)", ["member_id", "host", "role"])
GTID_EXECUTED = Gauge("mysql_gtid_executed", "GTID 执行的事务数量")
MGR_PRIMARY_MEMBER = Gauge("mysql_mgr_primary_member", "当前 MySQL MGR 主节点", ["primary_host"])
MGR_LAGGING_MEMBERS = Gauge("mysql_mgr_lagging_members", "MGR 复制落后事务数", ["member_id", "host"])
FETCH_TIME = Histogram("mysql_mgr_fetch_time_seconds", "获取 MySQL 监控数据所用时间")
MGR_RECOVERING_MEMBERS = Gauge("mysql_mgr_recovering_members", "处于 RECOVERING 状态的成员数量")
MGR_SINGLE_PRIMARY_MODE = Gauge("mysql_mgr_single_primary_mode", "MGR 是否处于单主模式 (1=ON, 0=OFF)")
MGR_CONFLICTS = Gauge("mysql_mgr_conflicts", "MGR 事务冲突次数")
GTID_ERRORS = Gauge("mysql_mgr_gtid_errors", "MGR GTID 错误数量")
TRANSACTIONS_COMMITTED = Gauge("mysql_mgr_transactions_committed", "提交的事务数量", ["member_id", "host"])
TRANSACTIONS_ROLLBACKED = Gauge("mysql_mgr_transactions_rolledback", "回滚的事务数量", ["member_id", "host"])

LAST_PRIMARY = None  # 记录上一次的主节点

def connect_mysql():
    """尝试连接 MySQL 数据库"""
    try:
        return pymysql.connect(**MYSQL_CONFIG)
    except Exception as e:
        logger.error(f"连接 MySQL 失败: {e}")
        return None

@FETCH_TIME.time()
def fetch_metrics():
    """从 MySQL 获取监控数据并更新指标"""
    global LAST_PRIMARY
    conn = connect_mysql()
    if not conn:
        return

    try:
        with conn.cursor() as cursor:
            # 获取 MGR 集群成员信息
            cursor.execute("SELECT * FROM performance_schema.replication_group_members;")
            group_members = cursor.fetchall()
            MGR_MEMBER_COUNT.set(len(group_members))

            recovering_count = 0  # 统计恢复中的节点数量
            for member in group_members:
                state = 1 if member["MEMBER_STATE"] == "ONLINE" else 0
                MGR_MEMBER_STATUS.labels(
                    member_id=member["MEMBER_ID"],
                    host=member["MEMBER_HOST"],
                    role=member["MEMBER_ROLE"]
                ).set(state)
                if member["MEMBER_STATE"] == "RECOVERING":
                    recovering_count += 1
            MGR_RECOVERING_MEMBERS.set(recovering_count)

            # 获取 GTID 执行状态
            cursor.execute("SELECT @@global.gtid_executed;")
            gtid_executed = cursor.fetchone()["@@global.gtid_executed"]
            GTID_EXECUTED.set(len(gtid_executed.split(",")))

            # 获取 GTID 错误
            cursor.execute("SELECT VARIABLE_VALUE FROM performance_schema.global_status WHERE VARIABLE_NAME='group_replication_gtid_errors';")
            gtid_errors = cursor.fetchone()
            if gtid_errors:
                GTID_ERRORS.set(int(gtid_errors["VARIABLE_VALUE"]))
            else:
                GTID_ERRORS.set(0)  # 如果没有数据，设置为 0
                logger.warning("没有找到 group_replication_gtid_errors 的值，假设为 0")

            # 获取当前 Primary 节点
            cursor.execute("SELECT VARIABLE_VALUE FROM performance_schema.global_status WHERE VARIABLE_NAME='group_replication_primary_member';")
            primary_member = cursor.fetchone()["VARIABLE_VALUE"]
            if LAST_PRIMARY and LAST_PRIMARY != primary_member:
                logger.warning(f"!MGR 主节点变更: {LAST_PRIMARY} -> {primary_member}")
            LAST_PRIMARY = primary_member
            MGR_PRIMARY_MEMBER.labels(primary_host=primary_member).set(1)

            # 获取复制延迟信息
            cursor.execute("""
                SELECT rgm.MEMBER_ID, rgm.MEMBER_HOST, rgms.COUNT_TRANSACTIONS_REMOTE_IN_APPLIER_QUEUE
                FROM performance_schema.replication_group_member_stats rgms
                JOIN performance_schema.replication_group_members rgm
                ON rgms.MEMBER_ID = rgm.MEMBER_ID;
            """)
            stats = cursor.fetchall()

            for row in stats:
                MGR_LAGGING_MEMBERS.labels(member_id=row["MEMBER_ID"], host=row["MEMBER_HOST"]).set(row["COUNT_TRANSACTIONS_REMOTE_IN_APPLIER_QUEUE"])

            # 获取 MGR 单主模式状态
            cursor.execute("SELECT VARIABLE_VALUE FROM performance_schema.global_variables WHERE VARIABLE_NAME='group_replication_single_primary_mode';")
            single_primary_mode = cursor.fetchone()["VARIABLE_VALUE"]
            MGR_SINGLE_PRIMARY_MODE.set(1 if single_primary_mode == "ON" else 0)

            # 获取 MGR 事务冲突情况，如果查询为空，设置默认值为 0
            cursor.execute("SELECT VARIABLE_VALUE FROM performance_schema.global_status WHERE VARIABLE_NAME='group_replication_conflicts_detected';")
            conflicts_result = cursor.fetchone()
            if conflicts_result:
                MGR_CONFLICTS.set(int(conflicts_result["VARIABLE_VALUE"]))
            else:
                MGR_CONFLICTS.set(0)  # 如果没有数据，设置为 0
                logger.warning("没有找到 group_replication_conflicts_detected 的值，假设为 0")

    except Exception as e:
        logger.error(f"获取监控数据时出错: {e}")
        logger.error(traceback.format_exc())
    finally:
        conn.close()

if __name__ == "__main__":
    start_http_server(8000)
    logger.info("Prometheus MySQL MGR Exporter 运行中，监听端口 8000...")
    while True:
        fetch_metrics()
        time.sleep(10)
