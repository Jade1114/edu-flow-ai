<!-- Teacher -->
<el-tab-pane label="教师管理" name="teacher">
                <div style="margin-bottom: 12px; display: flex; gap: 8px; align-items: center">
                    <el-button type="primary" @click="openTeacherDialog(undefined)">新增教师</el-button>
                    <el-input
                        v-model="teacherSearch"
                        placeholder="搜索工号、姓名和部门"
                        clearable
                        style="width: 240px"
                    />
                </div>
                <el-table :data="pagedTeachers" v-loading="loadingTeachers" border size="small">
                    <template #empty>
                        <el-empty description="暂无教师数据" />
                    </template>
                    <el-table-column prop="employeeNo" label="工号" width="100" />
                    <el-table-column prop="name" label="姓名" width="100" />
                    <el-table-column prop="department" label="部门" />
                    <el-table-column prop="title" label="职称" width="100" />
                    <el-table-column prop="maxWeeklyHours" label="最大周课时" width="100" />
                    <el-table-column prop="role" label="角色" width="100" />
                    <el-table-column label="状态" width="80">
                        <template #default="{ row }">
                            <ActiveStatusTag :status="row.status" />
                        </template>
                    </el-table-column>
                    <el-table-column label="操作" width="220">
                        <template #default="{ row }">
                            <el-button
                                size="small"
                                @click="
                                    router.push({
                                        name: 'AdminTeacherDetail',
                                        params: {
                                            id: row.id,
                                        },
                                        query: {
                                            from: route.fullPath,
                                        },
                                    })
                                "
                                >详情</el-button
                            >
                            <el-button
                                type="primary"
                                size="small"
                                :disabled="deletingTeacherId === row.id"
                                @click="openTeacherDialog(row)"
                                >编辑</el-button
                            >
                            <ConfirmDeleteButton
                                :loading="deletingTeacherId === row.id"
                                :disabled="deletingTeacherId === row.id"
                                @confirm="deleteTeacher(row.id)"
                                >删除教师</ConfirmDeleteButton
                            >
                        </template>
                    </el-table-column>
                </el-table>
                <el-pagination
                    v-model:current-page="teacherPage"
                    v-model:page-size="teacherPageSize"
                    :total="filteredTeachers.length"
                    :page-sizes="[5, 10, 20, 50]"
                    layout="total, sizes, prev, pager, next"
                    style="margin-top: 12px; justify-content: flex-end"
                />
            </el-tab-pane>
