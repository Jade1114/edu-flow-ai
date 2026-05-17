package com.yuy.eduflow.allocation;

import java.util.List;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface AllocationItemAdjustmentLogMapper {

	@Select("""
		SELECT COUNT(*)
		FROM allocation_item_adjustment_log
		WHERE scheme_id = #{schemeId}
		""")
	int countBySchemeId(Long schemeId);

	@Select("""
		SELECT id, scheme_id, item_id, teaching_task_id,
		       from_time_slot_id, to_time_slot_id,
		       from_classroom_id, to_classroom_id,
		       reason, created_by, created_at
		FROM allocation_item_adjustment_log
		WHERE scheme_id = #{schemeId}
		ORDER BY id DESC
		""")
	List<AllocationItemAdjustmentLog> findBySchemeId(Long schemeId);

	@Insert("""
		INSERT INTO allocation_item_adjustment_log (
		    scheme_id, item_id, teaching_task_id,
		    from_time_slot_id, to_time_slot_id,
		    from_classroom_id, to_classroom_id,
		    reason, created_by
		) VALUES (
		    #{schemeId}, #{itemId}, #{teachingTaskId},
		    #{fromTimeSlotId}, #{toTimeSlotId},
		    #{fromClassroomId}, #{toClassroomId},
		    #{reason}, #{createdBy}
		)
		""")
	@Options(useGeneratedKeys = true, keyProperty = "id")
	int insert(AllocationItemAdjustmentLog log);
}
