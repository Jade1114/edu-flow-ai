import { useCourses } from "../hooks/useCourses";
import CourseTable from "../ui/CourseTable";
import CourseDialog from "../ui/CourseDialog";

export default function CourseManager() {
  const c = useCourses();

  return (
    <>
      <CourseTable
        courses={c.paged}
        loading={c.loading}
        search={c.search}
        onSearchChange={c.setSearch}
        page={c.page}
        pageSize={c.pageSize}
        total={c.filtered.length}
        onPageChange={c.setPage}
        onPageSizeChange={c.setPageSize}
        deleting={c.deleting}
        onEdit={c.openDialog}
        onDelete={c.remove}
        onAdd={() => c.openDialog()}
      />
      {c.dialogOpen && (
        <CourseDialog
          form={c.form}
          onChange={c.setForm}
          saving={c.saving}
          onSave={c.save}
          onClose={c.closeDialog}
        />
      )}
    </>
  );
}
