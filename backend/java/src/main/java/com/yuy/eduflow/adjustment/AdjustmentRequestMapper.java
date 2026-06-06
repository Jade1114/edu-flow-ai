package com.yuy.eduflow.adjustment;

import java.util.List;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface AdjustmentRequestMapper {

    @Select("""
        SELECT id, assignment_id, teacher_id, reason, preferred_time_text,
               status, review_note, created_at, updated_at
        FROM adjustment_request
        WHERE id = #{id}
        """)
    AdjustmentRequest findById(Long id);

    @Select("""
        <script>
        SELECT id, assignment_id, teacher_id, reason, preferred_time_text,
               status, review_note, created_at, updated_at
        FROM adjustment_request
        WHERE 1 = 1
        <if test='status != null and status != ""'>
          AND status = #{status}
        </if>
        <if test='teacherId != null'>
          AND teacher_id = #{teacherId}
        </if>
        ORDER BY created_at DESC
        </script>
        """)
    List<AdjustmentRequest> findAll(
        @Param("status") String status,
        @Param("teacherId") Long teacherId
    );

    @Insert("""
        INSERT INTO adjustment_request (assignment_id, teacher_id, reason, preferred_time_text, status)
        VALUES (#{assignmentId}, #{teacherId}, #{reason}, #{preferredTimeText}, 'PENDING')
        """)
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(AdjustmentRequest request);

    @Update("""
        UPDATE adjustment_request
        SET status = #{status},
            review_note = #{reviewNote}
        WHERE id = #{id}
        """)
    int updateReview(@Param("id") Long id, @Param("status") String status, @Param("reviewNote") String reviewNote);

    @Delete("DELETE FROM adjustment_request WHERE id = #{id}")
    int delete(Long id);
}
