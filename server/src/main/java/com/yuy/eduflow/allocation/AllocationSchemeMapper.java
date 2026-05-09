package com.yuy.eduflow.allocation;

import java.util.List;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface AllocationSchemeMapper {

	@Select("""
		<script>
		SELECT id, task_id, scheme_name, summary, score, satisfied_summary,
		       conflict_summary, valid, status, created_at, updated_at
		FROM allocation_scheme
		WHERE 1 = 1
		<if test='taskId != null'>
		  AND task_id = #{taskId}
		</if>
		<if test='status != null and status != ""'>
		  AND status = #{status}
		</if>
		ORDER BY id DESC
		</script>
		""")
	List<AllocationScheme> findAll(@Param("taskId") Long taskId, @Param("status") String status);

	@Select("""
		SELECT id, task_id, scheme_name, summary, score, satisfied_summary,
		       conflict_summary, valid, status, created_at, updated_at
		FROM allocation_scheme
		WHERE id = #{id}
		""")
	AllocationScheme findById(Long id);

	@Insert("""
		INSERT INTO allocation_scheme (
		    task_id, scheme_name, summary, score, satisfied_summary,
		    conflict_summary, valid, status
		)
		VALUES (
		    #{taskId}, #{schemeName}, #{summary}, #{score}, #{satisfiedSummary},
		    #{conflictSummary}, #{valid}, #{status}
		)
		""")
	@Options(useGeneratedKeys = true, keyProperty = "id")
	int insert(AllocationScheme scheme);

	@Update("""
		UPDATE allocation_scheme
		SET task_id = #{taskId},
		    scheme_name = #{schemeName},
		    summary = #{summary},
		    score = #{score},
		    satisfied_summary = #{satisfiedSummary},
		    conflict_summary = #{conflictSummary},
		    valid = #{valid},
		    status = #{status}
		WHERE id = #{id}
		""")
	int update(AllocationScheme scheme);

	@Update("""
		UPDATE allocation_scheme
		SET status = 'REJECTED'
		WHERE id = #{id}
		""")
	int reject(Long id);
}
