import logging

from django.contrib import admin, messages
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from task.models import Content, RSSTask, Task, TaskStatus
from task.utils.scheduler import remove_job, monitor

logger = logging.getLogger('admin')


@admin.register(TaskStatus)
class TaskStatusAdmin(admin.ModelAdmin):
    list_display = [
        'task_id', 'task_name', 'last_run', 'short_last_status', 'task_status',
        'task_type'
    ]
    list_editable = ['task_status']
    list_per_page = 10
    list_display_links = None

    actions_on_top = True

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class TaskResource(resources.ModelResource):
    class Meta:
        model = Task
        import_id_fields = ('name', )
        exclude = ('id', )
        skip_unchanged = True
        report_skipped = True


@admin.register(Task)
class TaskAdmin(ImportExportModelAdmin):
    resource_class = TaskResource

    list_display = [
        'id', 'name', 'url', 'frequency', 'selector', 'create_time',
        'is_chrome', 'regular_expression', 'rule', 'headers'
    ]
    list_editable = ('name', 'url', 'frequency', 'is_chrome',
                     'regular_expression', 'rule', 'headers', 'selector')
    filter_horizontal = ('notification', )

    list_per_page = 10

    def has_delete_permission(self, request, obj=None):
        return False

    def redefine_delete_selected(self, request, obj):
        for o in obj.all():
            id = o.id
            remove_job(id)

            TaskStatus.objects.filter(task_id=id, task_type='html').delete()
            Content.objects.filter(task_id=id, task_type='html').delete()

            o.delete()
            logger.info('task_{}删除'.format(id))

        messages.add_message(request, messages.SUCCESS, '删除成功')

    redefine_delete_selected.short_description = '删除'
    redefine_delete_selected.icon = 'el-icon-delete'
    redefine_delete_selected.style = 'color:white;background:red'

    def run_now_button(self, request, obj):
        names = []
        for o in obj.all():
            id = o.id
            names.append(o.name)
            monitor(id, 'html')
            logger.info('task_{}执行成功'.format(id))

        messages.add_message(request, messages.SUCCESS, '{} 执行成功'.format(','.join(names)))

    run_now_button.short_description = '立即执行'
    run_now_button.type = 'info'
    run_now_button.icon = 'el-icon-caret-right'

    actions = ['redefine_delete_selected', 'run_now_button']


class RSSTaskResource(resources.ModelResource):
    class Meta:
        model = RSSTask
        import_id_fields = ('name', )
        exclude = ('id', )
        skip_unchanged = True
        report_skipped = True


@admin.register(RSSTask)
class RSSTaskAdmin(ImportExportModelAdmin):
    resource_class = RSSTaskResource

    list_display = ['id', 'name', 'url', 'frequency', 'create_time']
    list_editable = ('name', 'url', 'frequency')
    filter_horizontal = ('notification', )

    list_per_page = 10

    def has_delete_permission(self, request, obj=None):
        return False

    def redefine_delete_selected(self, request, obj):
        for o in obj.all():
            id = o.id
            remove_job(id, 'rss')

            TaskStatus.objects.filter(task_id=id, task_type='rss').delete()
            Content.objects.filter(task_id=id, task_type='rss').delete()

            o.delete()
            logger.info('task_RSS{}删除'.format(id))

        messages.add_message(request, messages.SUCCESS, '删除成功')

    redefine_delete_selected.short_description = '删除'
    redefine_delete_selected.icon = 'el-icon-delete'
    redefine_delete_selected.style = 'color:white;background:red'

    actions = ['redefine_delete_selected']
