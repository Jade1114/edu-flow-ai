import { useClassGroups } from "../hooks/useClassGroups";
import ClassGroupTable from "../ui/ClassGroupTable";
import ClassGroupDialog from "../ui/ClassGroupDialog";

export default function ClassGroupManager() {
  const g = useClassGroups();
  return (
    <>
      <ClassGroupTable groups={g.paged} loading={g.loading} search={g.search} onSearchChange={g.setSearch} page={g.page} pageSize={g.pageSize} total={g.filtered.length} onPageChange={g.setPage} onPageSizeChange={g.setPageSize} deleting={g.deleting} onEdit={g.openDialog} onDelete={g.remove} onAdd={() => g.openDialog()} />
      {g.dialogOpen && <ClassGroupDialog form={g.form} onChange={g.setForm} saving={g.saving} onSave={g.save} onClose={g.closeDialog} />}
    </>
  );
}
