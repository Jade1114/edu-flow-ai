package com.yuy.eduflow.timeslot;

import java.util.List;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface TimeSlotMapper {

	@Select("""
		<script>
		SELECT id, week_number, day_of_week, period_index, label, created_at, updated_at
		FROM time_slot
		WHERE 1 = 1
		<if test='weekNumber != null'>
		  AND week_number = #{weekNumber}
		</if>
		<if test='dayOfWeek != null'>
		  AND day_of_week = #{dayOfWeek}
		</if>
		ORDER BY week_number ASC, day_of_week ASC, period_index ASC
		</script>
		""")
	List<TimeSlot> findAll(@Param("weekNumber") Integer weekNumber, @Param("dayOfWeek") Integer dayOfWeek);

	@Select("""
		SELECT id, week_number, day_of_week, period_index, label, created_at, updated_at
		FROM time_slot
		WHERE id = #{id}
		""")
	TimeSlot findById(Long id);

	@Insert("""
		INSERT INTO time_slot (week_number, day_of_week, period_index, label)
		VALUES (#{weekNumber}, #{dayOfWeek}, #{periodIndex}, #{label})
		""")
	@Options(useGeneratedKeys = true, keyProperty = "id")
	int insert(TimeSlot timeSlot);

	@Update("""
		UPDATE time_slot
		SET week_number = #{weekNumber},
		    day_of_week = #{dayOfWeek},
		    period_index = #{periodIndex},
		    label = #{label}
		WHERE id = #{id}
		""")
	int update(TimeSlot timeSlot);

	@Delete("""
		DELETE FROM time_slot
		WHERE id = #{id}
		""")
	int delete(Long id);
}
