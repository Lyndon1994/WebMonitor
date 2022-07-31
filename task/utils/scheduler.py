import logging
import traceback
from datetime import datetime, timedelta

import markdown
from apscheduler.jobstores.base import JobLookupError
from func_timeout.exceptions import FunctionTimedOut

from task.models import Content, RSSTask, Task, TaskStatus
from task.utils.extract_info import get_content, get_rss_content
from task.utils.notification.notification_handler import new_handler
from task.utils.rule import is_changed
from task.views import scheduler

logger = logging.getLogger('main')


# 部分通知方式出错异常
class PartNotificationError(Exception):
    pass


def wraper_rss_msg(item):
    title = item['title']
    link = item['link']

    res = '''[{}]({})'''.format(title, link)
    return res


def send_message(content, header, notifications):
    if len(notifications) == 0:
        raise Exception('通知方式为空')

    total = 0
    fail = 0

    exception_content = ''
    for notification in notifications:
        total += 1

        type = notification.type
        notification_detail = notification.content

        try:
            if type == 0:
                handler = new_handler('mail')
                content = markdown.markdown(content,
                                            output_format='html5',
                                            extensions=['extra'])
                handler.send(notification_detail, header, content)
        except Exception as e:
            fail += 1
            exception_content += 'Mail Exception: {};'.format(repr(e))

        try:
            if type == 1:
                handler = new_handler('wechat')
                handler.send(notification_detail, header, content)
        except Exception as e:
            fail += 1
            exception_content += 'Wechat Exception: {};'.format(repr(e))

        try:
            if type == 2:
                handler = new_handler('pushover')
                handler.send(notification_detail, header, content)
        except Exception as e:
            fail += 1
            exception_content += 'Pushover Exception: {};'.format(repr(e))

        try:
            if type == 3:
                handler = new_handler('bark')
                handler.send(notification_detail, header, content)
        except Exception as e:
            fail += 1
            exception_content += 'Bark Exception: {};'.format(repr(e))

        try:
            if type == 4:
                handler = new_handler('custom')
                handler.send(notification_detail, header, content)
        except Exception as e:
            fail += 1
            exception_content += 'Custom Exception: {};'.format(repr(e))

        try:
            if type == 5:
                handler = new_handler('slack')
                handler.send(notification_detail, header, content)
        except Exception as e:
            fail += 1
            exception_content += 'Slack Exception: {};'.format(repr(e))

        try:
            if type == 6:
                handler = new_handler('telegram')
                handler.send(notification_detail, header, content)
        except Exception as e:
            fail += 1
            exception_content += 'Telegram Exception: {};'.format(repr(e))

    if fail > 0:
        if fail < total:
            raise PartNotificationError('监测到变化，部分通知方式发送错误：' +
                                        exception_content)
        else:
            raise Exception('监测到变化，但发送通知错误：' + exception_content)


def monitor(id, type):
    status = ''
    global_content = None
    last = None
    try:
        if type == 'html':
            task = Task.objects.get(pk=id)
            name = task.name
            url = task.url
            selector_type = task.selector_type
            selector = task.selector
            is_chrome = task.is_chrome
            content_template = task.template

            notifications = [i for i in task.notification.iterator()]

            regular_expression = task.regular_expression
            rule = task.rule
            headers = task.headers

            try:
                last = Content.objects.get(task_id=id, task_type=type)
            except Exception:
                last = Content(task_id=id)

            last_content = last.content
            content = get_content(url, is_chrome, selector_type, selector,
                                  content_template, regular_expression,
                                  headers)
            global_content = content
            status_code = is_changed(rule, content, last_content)
            logger.info(
                'rule: {}, content: {}, last_content: {}, status_code: {}'.
                format(rule, content[:300], last_content[:300], status_code))
            if status_code == 1:
                status = '监测到变化，但未命中规则，最新值为{}'.format(content)
                last.content = content
                last.save()
            elif status_code == 2:
                status = '监测到变化，且命中规则，最新值为{}'.format(content)
                send_message(content, name, notifications)
                last.content = content
                last.save()
            elif status_code == 3:
                status = '监测到变化，最新值为{}'.format(content)
                send_message(content, name, notifications)
                last.content = content
                last.save()
            elif status_code == 0:
                status = '成功执行但未监测到变化，当前值为{}'.format(content)
            elif status_code == 4:
                status = '总是发送消息，最新值为{}'.format(content)
                send_message(content, name, notifications)
                last.content = content
                last.save()
        elif type == 'rss':
            rss_task = RSSTask.objects.get(id=id)
            url = rss_task.url
            name = rss_task.name

            notifications = [i for i in rss_task.notification.iterator()]

            try:
                last = Content.objects.get(task_id=id, task_type=type)
            except Exception:
                last = Content(task_id=id, task_type='rss')

            last_guid = last.content
            item = get_rss_content(url)
            global_content = item['guid']
            if item['guid'] != last_guid:
                content = wraper_rss_msg(item)
                send_message(content, name, notifications)
                last.content = item['guid']
                last.save()
                status = '监测到变化，最新值：' + item['guid']
            else:
                status = '成功执行但未监测到变化，当前值为{}'.format(last_guid)

    except FunctionTimedOut:
        logger.error(traceback.format_exc())
        status = '解析RSS超时'
    except PartNotificationError as e:
        logger.error(traceback.format_exc())
        status = repr(e)
        last.content = global_content
        last.save()
    except Exception as e:
        logger.error(traceback.format_exc())
        status = repr(e)

    task_status = TaskStatus.objects.get(task_id=id, task_type=type)
    task_status.last_run = datetime.now()
    task_status.last_status = status
    task_status.save()


def add_job(id, interval, type='html'):
    task_id = ''
    if type == 'html':
        task_id = id
    elif type == 'rss':
        task_id = 'rss{}'.format(id)
    try:
        scheduler.remove_job(job_id='task_{}'.format(task_id))
        logger.info('remove job:task_{} success.'.format(task_id))
    except Exception as e:
        logger.error('remove job:task_{} failed. error:{}'.format(task_id, e))
        pass
    crons = str(interval).split()
    if len(crons) == 1:
        if float(crons[0]) < 0:
            raise Exception('频率不能为负数')
        else:
            scheduler.add_job(func=monitor,
                            args=(
                                id,
                                type,
                            ),
                            trigger='interval',
                            minutes=float(crons[0]),
                            id='task_{}'.format(task_id),
                            replace_existing=True)
    elif len(crons) == 2:
        scheduler.add_job(func=monitor,
            args=(
                id,
                type,
            ),
            trigger='date',
            run_date=interval,
            id='task_{}'.format(task_id),
            replace_existing=True)
    elif len(crons) == 5:
        scheduler.add_job(func=monitor,
                        args=(
                            id,
                            type,
                        ),
                        trigger='cron',
                        minute=crons[0],
                        hour=crons[1],
                        day=crons[2],
                        month=crons[3],
                        day_of_week=crons[4],
                        id='task_{}'.format(task_id),
                        replace_existing=True)
    elif len(crons) == 7:
        scheduler.add_job(func=monitor,
                args=(
                    id,
                    type,
                ),
                trigger='cron',
                second=crons[0],
                minute=crons[1],
                hour=crons[2],
                day=crons[3],
                month=crons[4],
                day_of_week=crons[5],
                year=crons[6],
                id='task_{}'.format(task_id),
                replace_existing=True)
    else:
        raise Exception('crontab格式错误')
    logger.info('添加定时任务task_{}: {}'.format(task_id, scheduler.get_job('task_{}'.format(task_id))))


def remove_job(id, type='html'):
    task_id = ''

    if type == 'html':
        task_id = id
    elif type == 'rss':
        task_id = 'rss{}'.format(id)

    try:
        scheduler.remove_job('task_{}'.format(task_id))
        logger.info('删除定时任务task_{}'.format(task_id))
    except JobLookupError as e:
        logger.info(e)
        logger.info('task_{}不存在'.format(task_id))
