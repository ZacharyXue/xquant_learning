import logging
import os
import time
from logging.handlers import RotatingFileHandler

# 生成全局唯一的执行时间戳，用于创建日志文件夹
EXECUTION_TIMESTAMP = time.strftime('%Y%m%d')

class LogManager:
    def __init__(self, name, log_dir="logs", max_bytes=10*1024*1024, backup_count=5):
        """
        初始化日志管理器
        
        参数:
        name: 日志名称
        log_dir: 日志存储目录
        max_bytes: 单个日志文件最大字节数
        backup_count: 保留的备份文件数量
        """
        # 创建logger对象
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)  # 默认设置为最低级别，让handler来控制
        
        # 避免重复添加handler
        if not self.logger.handlers:
            # 创建基于时间戳的日志目录结构
            timestamp_log_dir = os.path.join(log_dir, EXECUTION_TIMESTAMP)
            if not os.path.exists(timestamp_log_dir):
                os.makedirs(timestamp_log_dir)
            
            # 格式化日志输出，移除调用方信息
            formatter = logging.Formatter(
                '%(asctime)s - [%(name)s] - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            # 创建控制台handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)  # 控制台输出INFO级别及以上
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
            
            # 创建文件handler (支持按大小分割)
            log_file = os.path.join(timestamp_log_dir, f"{name}.log")
            file_handler = RotatingFileHandler(
                log_file, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)  # 文件记录DEBUG级别及以上
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def debug(self, message):
        """记录debug级别日志"""
        self.logger.debug(message)
    
    def info(self, message):
        """记录info级别日志"""
        self.logger.info(message)
    
    def warn(self, message):
        """记录warn级别日志"""
        self.logger.warn(message)

    def warning(self, message):
        """记录warning级别日志 (warn的别名)"""
        self.logger.warn(message)
    
    def error(self, message):
        """记录error级别日志"""
        self.logger.error(message)
    
    def critical(self, message):
        """记录critical级别日志"""
        self.logger.critical(message)

# 提供一个方便的函数来获取日志实例
def get_logger(name, log_dir="logs", max_bytes=10*1024*1024, backup_count=5):
    """
    获取一个日志实例
    
    参数:
    name: 日志名称
    log_dir: 日志存储目录
    max_bytes: 单个日志文件最大字节数
    backup_count: 保留的备份文件数量
    
    返回:
    LogManager实例
    """
    return LogManager(name, log_dir, max_bytes, backup_count)

if __name__ == "__main__":
    # 示例用法
    logger = get_logger("test_logger")
    logger.debug("这是一条debug日志")
    logger.info("这是一条info日志")
    logger.warn("这是一条warn日志")
    logger.error("这是一条error日志")
    logger.critical("这是一条critical日志")