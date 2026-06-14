import { useTeachers } from "../hooks/useTeachers";
import TeacherTable from "../ui/TeacherTable";
import TeacherDialog from "../ui/TeacherDialog";

export default function TeacherManager() {
  const t = useTeachers();
  return (
    <>
      <TeacherTable teachers={t.paged} loading={t.loading} search={t.search} onSearchChange={t.setSearch} statusFilter={t.statusFilter} onStatusFilterChange={t.setStatusFilter} page={t.page} pageSize={t.pageSize} total={t.filtered.length} onPageChange={t.setPage} onPageSizeChange={t.setPageSize} deleting={t.deleting} onEdit={t.openDialog} onDelete={t.remove} onAdd={() => t.openDialog()} batch={t.batch} />
      {t.dialogOpen && <TeacherDialog form={t.form} onChange={t.setForm} saving={t.saving} onSave={t.save} onClose={t.closeDialog} />}
    </>
  );
}
