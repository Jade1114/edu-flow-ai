package com.yuy.eduflow.allocation;

import com.yuy.eduflow.rag.TeacherProfileVectorService;
import java.util.List;
import lombok.extern.slf4j.Slf4j;
import com.yuy.eduflow.enums.ActiveStatus;
import org.springframework.stereotype.Service;

@Slf4j
@Service
public class AllocationRagContextService {
	
	private static final int DEFAULT_TOP_K = 5;

	private final AllocationTaskService allocationTaskService;
	private final TeacherProfileVectorService teacherProfileVectorService;
	private final RagQueryBuilderService ragQueryBuilderService;

	public AllocationRagContextService(
		AllocationTaskService allocationTaskService,
		TeacherProfileVectorService teacherProfileVectorService,
		RagQueryBuilderService ragQueryBuilderService
	) {
		this.allocationTaskService = allocationTaskService;
		this.teacherProfileVectorService = teacherProfileVectorService;
		this.ragQueryBuilderService = ragQueryBuilderService;
	}

	public AllocationRagContext buildContext(Long taskId, Integer topK) {
		log.info("=== RAG buildContext() start === taskId={}, topK={}", taskId, topK);
		AllocationTask task = allocationTaskService.findById(taskId);
		int limit = topK == null ? DEFAULT_TOP_K : topK;
		String query = ragQueryBuilderService.buildQuery(task);
		log.info("RAG query built, length={}", query.length());
		long t0 = System.currentTimeMillis();
		log.info("RAG searching Qdrant with topK={}...", limit);
		long start = System.currentTimeMillis();
		List<AllocationRagTeacherResult> teachers = teacherProfileVectorService.search(query, limit, ActiveStatus.ACTIVE.code()).stream()
			.map(AllocationRagTeacherResult::from)
			.toList();
		long elapsed = System.currentTimeMillis() - t0;
		log.info("RAG search done in {}ms, found {} teachers", elapsed, teachers.size());
		for (AllocationRagTeacherResult t : teachers) {
			log.info("  >> teacherId={}, name={}, score={}, vectorText=[{}]",
				t.teacherId(), t.teacherName(), t.score(),
				t.vectorText() != null ? t.vectorText().substring(0, Math.min(80, t.vectorText().length())) : null);
		}
		return new AllocationRagContext(task.getId(), task.getName(), query, limit, teachers);
	}
}
