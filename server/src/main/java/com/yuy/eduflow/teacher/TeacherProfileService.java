package com.yuy.eduflow.teacher;

import com.yuy.eduflow.rag.TeacherProfileVectorService;
import java.util.ArrayList;
import java.util.List;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

@Slf4j
@Service
public class TeacherProfileService {
	private final TeacherService teacherService;
	private final TeacherProfileMapper teacherProfileMapper;
	private final TeacherProfileVectorService teacherProfileVectorService;

	public TeacherProfileService(
		TeacherService teacherService,
		TeacherProfileMapper teacherProfileMapper,
		TeacherProfileVectorService teacherProfileVectorService
	) {
		this.teacherService = teacherService;
		this.teacherProfileMapper = teacherProfileMapper;
		this.teacherProfileVectorService = teacherProfileVectorService;
	}

	public TeacherProfile findByTeacherId(Long teacherId) {
		teacherService.findById(teacherId);
		return teacherProfileMapper.findByTeacherId(teacherId);
	}

	public TeacherProfile save(Long teacherId, TeacherProfileRequest request) {
		log.info("=== save() start === teacherId={}", teacherId);
		log.info("request={}", request);
		Teacher teacher = teacherService.findById(teacherId);
		log.info("teacher found: id={}, name={}", teacher.getId(), teacher.getName());
		TeacherProfile profile = toProfile(teacher, request);
		log.debug("vectorText built: [{}]", profile.getVectorText());
		TeacherProfile existing = teacherProfileMapper.findByTeacherId(teacherId);
		log.info("existing profile: {}", existing);
		if (existing == null) {
			int rows = teacherProfileMapper.insert(profile);
			log.info("INSERT affected rows={}, generated id={}", rows, profile.getId());
		} else {
			int rows = teacherProfileMapper.updateByTeacherId(profile);
			log.info("UPDATE affected rows={}", rows);
		}
		TeacherProfile result = teacherProfileVectorService.indexTeacherProfile(teacherId);
		if (result == null) {
			log.warn("indexTeacherProfile returned null for teacherId={}, using un-indexed profile", teacherId);
			result = existing != null ? existing : profile;
		}
		log.info("=== save() end === profile={}", result);
		return result;
	}

    private TeacherProfile toProfile(Teacher teacher, TeacherProfileRequest request) {
        TeacherProfile profile = new TeacherProfile();
        profile.setTeacherId(teacher.getId());
        profile.setAvailableTimeText(clean(request.availableTimeText()));
        profile.setUnavailableTimeText(clean(request.unavailableTimeText()));
        profile.setWorkloadRequirement(clean(request.workloadRequirement()));
        profile.setSpecialNote(clean(request.specialNote()));
        profile.setVectorText(buildVectorText(teacher, profile));
        profile.setVectorIndexed(false);
        return profile;
    }

    private String buildVectorText(Teacher teacher, TeacherProfile profile) {
        List<String> lines = new ArrayList<>();
        if (StringUtils.hasText(profile.getAvailableTimeText())) {
            lines.add(teacher.getName() + "可用时间：" + profile.getAvailableTimeText() + "。");
        }
        if (StringUtils.hasText(profile.getUnavailableTimeText())) {
            lines.add(teacher.getName() + "不可用时间：" + profile.getUnavailableTimeText() + "。");
        }
        if (StringUtils.hasText(profile.getWorkloadRequirement())) {
            lines.add(teacher.getName() + "课时要求：" + profile.getWorkloadRequirement() + "。");
        }
        if (StringUtils.hasText(profile.getSpecialNote())) {
            lines.add(teacher.getName() + "特殊说明：" + profile.getSpecialNote() + "。");
        }
        return String.join("\n", lines);
    }

	private String clean(String value) {
		return StringUtils.hasText(value) ? value.trim() : null;
	}
}
