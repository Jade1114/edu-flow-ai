import { useClassrooms } from "../hooks/useClassrooms";
import ClassroomTable from "../ui/ClassroomTable";
import ClassroomDialog from "../ui/ClassroomDialog";

export default function ClassroomManager() {
  const room = useClassrooms();

  return (
    <>
      <ClassroomTable
        classrooms={room.paged}
        loading={room.loading}
        search={room.search}
        onSearchChange={room.setSearch}
        statusFilter={room.statusFilter}
        onStatusFilterChange={room.setStatusFilter}
        page={room.page}
        pageSize={room.pageSize}
        total={room.filtered.length}
        onPageChange={room.setPage}
        onPageSizeChange={room.setPageSize}
        deleting={room.deleting}
        onEdit={room.openDialog}
        onDelete={room.remove}
        onAdd={() => room.openDialog()}
        batch={room.batch}
      />
      {room.dialogOpen && (
        <ClassroomDialog
          form={room.form}
          onChange={room.setForm}
          saving={room.saving}
          onSave={room.save}
          onClose={room.closeDialog}
        />
      )}
    </>
  );
}
