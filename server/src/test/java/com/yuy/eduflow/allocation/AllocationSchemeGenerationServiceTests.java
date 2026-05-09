package com.yuy.eduflow.allocation;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.yuy.eduflow.conflict.ConflictCheckResult;
import com.yuy.eduflow.conflict.ConflictCheckResultMapper;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

class AllocationSchemeGenerationServiceTests {

	@Test
	void persistsGeneratedSchemesAndWritesTeacherTimeConflicts() {
		AllocationGenerateParseService parseService = mock(AllocationGenerateParseService.class);
		AllocationSchemeMapper schemeMapper = mock(AllocationSchemeMapper.class);
		AllocationItemMapper itemMapper = mock(AllocationItemMapper.class);
		ConflictCheckResultMapper conflictCheckResultMapper = mock(ConflictCheckResultMapper.class);
		AllocationSchemeGenerationService service = new AllocationSchemeGenerationService(
			parseService,
			schemeMapper,
			itemMapper,
			conflictCheckResultMapper,
			new AllocationSchemeConflictDetector()
		);
		Map<Long, AllocationScheme> persistedSchemes = stubSchemeMapper(schemeMapper);
		List<ItemConflictState> updatedItems = stubItemMapper(itemMapper);
		when(parseService.generateParsePreview(1L, 5)).thenReturn(new AllocationParsePreview(
			1L,
			"测试分课任务",
			"{\"schemes\":[]}",
			List.of(new AllocationParsedScheme(
				"方案一",
				"摘要",
				88,
				"满足要求",
				List.of(
					new AllocationParsedItem(1L, 1L, 1L, 1L, 1L),
					new AllocationParsedItem(2L, 2L, 1L, 2L, 1L)
				)
			)),
			List.of()
		));

		AllocationGenerateResult result = service.generateSchemes(1L, 5);

		assertThat(result.taskId()).isEqualTo(1L);
		assertThat(result.schemeCount()).isEqualTo(1);
		assertThat(result.schemes()).hasSize(1);
		assertThat(result.schemes().getFirst().getValid()).isFalse();
		assertThat(result.schemes().getFirst().getConflictSummary())
			.isEqualTo("发现 2 条冲突记录：教师时间冲突 2 条");
		assertThat(persistedSchemes.get(11L).getStatus()).isEqualTo("CANDIDATE");
		assertThat(updatedItems).hasSize(2);
		assertThat(updatedItems)
			.extracting(ItemConflictState::valid)
			.containsExactly(false, false);
		assertThat(updatedItems)
			.extracting(ItemConflictState::conflictMessage)
			.allSatisfy(message -> assertThat(message).contains("教师时间冲突", "涉及明细ID：101, 102"));

		ArgumentCaptor<ConflictCheckResult> resultCaptor = ArgumentCaptor.forClass(ConflictCheckResult.class);
		verify(conflictCheckResultMapper, times(2)).insert(resultCaptor.capture());
		assertThat(resultCaptor.getAllValues())
			.extracting(ConflictCheckResult::getBizType)
			.containsExactly("ALLOCATION_ITEM", "ALLOCATION_ITEM");
		assertThat(resultCaptor.getAllValues())
			.extracting(ConflictCheckResult::getBizId)
			.containsExactly(101L, 102L);
		assertThat(resultCaptor.getAllValues())
			.extracting(ConflictCheckResult::getConflictType)
			.containsExactly(AllocationSchemeConflictDetector.TEACHER_TIME, AllocationSchemeConflictDetector.TEACHER_TIME);
		assertThat(resultCaptor.getAllValues())
			.extracting(ConflictCheckResult::getResolved)
			.containsExactly(false, false);
		verify(schemeMapper).rejectCandidatesByTaskId(1L);
		verify(schemeMapper).updateConflictState(eq(11L), eq(false), eq("发现 2 条冲突记录：教师时间冲突 2 条"));
	}

	private Map<Long, AllocationScheme> stubSchemeMapper(AllocationSchemeMapper schemeMapper) {
		AtomicLong nextSchemeId = new AtomicLong(10);
		Map<Long, AllocationScheme> schemes = new LinkedHashMap<>();
		when(schemeMapper.insert(any(AllocationScheme.class))).thenAnswer(invocation -> {
			AllocationScheme scheme = invocation.getArgument(0);
			scheme.setId(nextSchemeId.incrementAndGet());
			schemes.put(scheme.getId(), copyScheme(scheme));
			return 1;
		});
		when(schemeMapper.updateConflictState(any(), any(), any())).thenAnswer(invocation -> {
			Long id = invocation.getArgument(0);
			AllocationScheme scheme = schemes.get(id);
			scheme.setValid(invocation.getArgument(1));
			scheme.setConflictSummary(invocation.getArgument(2));
			return 1;
		});
		when(schemeMapper.findById(any())).thenAnswer(invocation -> copyScheme(schemes.get(invocation.getArgument(0))));
		return schemes;
	}

	private List<ItemConflictState> stubItemMapper(AllocationItemMapper itemMapper) {
		AtomicLong nextItemId = new AtomicLong(100);
		List<ItemConflictState> updatedItems = new ArrayList<>();
		when(itemMapper.insert(any(AllocationItem.class))).thenAnswer(invocation -> {
			AllocationItem item = invocation.getArgument(0);
			item.setId(nextItemId.incrementAndGet());
			return 1;
		});
		when(itemMapper.updateConflictState(any(), any(), any())).thenAnswer(invocation -> {
			updatedItems.add(new ItemConflictState(
				invocation.getArgument(0),
				invocation.getArgument(1),
				invocation.getArgument(2)
			));
			return 1;
		});
		return updatedItems;
	}

	private AllocationScheme copyScheme(AllocationScheme source) {
		AllocationScheme scheme = new AllocationScheme();
		scheme.setId(source.getId());
		scheme.setTaskId(source.getTaskId());
		scheme.setSchemeName(source.getSchemeName());
		scheme.setSummary(source.getSummary());
		scheme.setScore(source.getScore());
		scheme.setSatisfiedSummary(source.getSatisfiedSummary());
		scheme.setConflictSummary(source.getConflictSummary());
		scheme.setValid(source.getValid());
		scheme.setStatus(source.getStatus());
		return scheme;
	}

	private record ItemConflictState(Long itemId, Boolean valid, String conflictMessage) {
	}
}
