package com.yuy.eduflow.teacher;

import com.yuy.eduflow.rag.TeacherProfileVectorService;
import java.util.ArrayList;
import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

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
		Teacher teacher = teacherService.findById(teacherId);
		TeacherProfile profile = toProfile(teacher, request);
		TeacherProfile existing = teacherProfileMapper.findByTeacherId(teacherId);
		if (existing == null) {
			teacherProfileMapper.insert(profile);
		} else {
			teacherProfileMapper.updateByTeacherId(profile);
		}
		return teacherProfileVectorService.indexTeacherProfile(teacherId);
	}

	private TeacherProfile toProfile(Teacher teacher, TeacherProfileRequest request) {
		TeacherProfile profile = new TeacherProfile();
		profile.setTeacherId(teacher.getId());
		profile.setSkillText(clean(request.skillText()));
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
		if (StringUtils.hasText(profile.getSkillText())) {
			lines.add(teacher.getName() + "擅长" + profile.getSkillText() + "。");
		}
		if (StringUtils.hasText(profile.getAvailableTimeText())) {
			lines.add("可用时间：" + profile.getAvailableTimeText() + "。");
		}
		if (StringUtils.hasText(profile.getUnavailableTimeText())) {
			lines.add("不可用时间：" + profile.getUnavailableTimeText() + "。");
		}
		if (StringUtils.hasText(profile.getWorkloadRequirement())) {
			lines.add("课时要求：" + profile.getWorkloadRequirement() + "。");
		}
		if (StringUtils.hasText(profile.getSpecialNote())) {
			lines.add("特殊说明：" + profile.getSpecialNote() + "。");
		}
		return String.join("\n", lines);
	}

	private String clean(String value) {
		return StringUtils.hasText(value) ? value.trim() : null;
	}
}
