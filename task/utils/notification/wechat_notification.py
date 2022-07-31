
import json
import logging

import requests
import markdownify

from task.utils.notification.notification import Notification

logger = logging.getLogger('main')


class WechatNotification(Notification):
    def send(self, to, header, content):
        if to == '默认':
            logger.error('没有设置Server酱 SCKEY，无法发送微信通知')
            raise Exception('没有设置Server酱 SCKEY，无法发送微信通知')
        content = markdownify.markdownify(content, heading_style="ATX")
        data = {
            'title': header[:32],
            'text': header,
            'desp': content,
            'short': content[:62],
        }
        url = 'https://sctapi.ftqq.com/{}.send'.format(to)
        r = requests.post(url, data=data)

        res = json.loads(r.text)
        if res['data']['errno'] != 0:
            raise Exception(res['data']['errmsg'])
        logger.info('Send Wechat msg success!')
