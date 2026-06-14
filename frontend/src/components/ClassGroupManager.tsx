import { useClassGroups } from "../hooks/useClassGroups";
import ClassGroupTable from "../ui/ClassGroupTable";
import ClassGroupDialog from "../ui/ClassGroupDialog";

export default function ClassGroupManager() {
  const g = useClassGroups();
  return (
    <>
      <ClassGroupTable
        groups={g.paged}
        loading={g.loading}
        search={g.search}
        onSearchChange={g.setSearch}
        gradeFilter={g.gradeFilter}
        majorFilter={g.majorFilter}
        departmentFilter={g.departmentFilter}
        gradeOptions={g.gradeOptions}
        majorOptions={g.majorOptions}
        departmentOptions={g.departmentOptions}
        onGradeFilterChange={g.setGradeFilter}
        onMajorFilterChange={g.setMajorFilter}
        onDepartmentFilterChange={g.setDepartmentFilter}
        hasFilter={g.hasFilter}
        onResetFilters={g.resetFilters}
        page={g.page}
        pageSize={g.pageSize}
        total={g.filtered.length}
        totalStudents={g.totalStudents}
        onPageChange={g.setPage}
        onPageSizeChange={g.setPageSize}
        deleting={g.deleting}
        onEdit={g.openDialog}
        onDelete={g.remove}
        onAdd={() => g.openDialog()}
        batch={g.batch}
      />
      {g.dialogOpen && <ClassGroupDialog form={g.form} onChange={g.setForm} saving={g.saving} onSave={g.save} onClose={g.closeDialog} />}
    </>
  );
}
