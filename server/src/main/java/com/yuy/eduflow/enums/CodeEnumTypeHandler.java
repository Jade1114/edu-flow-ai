package com.yuy.eduflow.enums;

import java.sql.CallableStatement;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import org.apache.ibatis.type.BaseTypeHandler;
import org.apache.ibatis.type.JdbcType;

/**
 * 通用 CodeEnum TypeHandler，将枚举按 code 字段与数据库 VARCHAR 互转。
 */
public abstract class CodeEnumTypeHandler<E extends Enum<E> & CodeEnum> extends BaseTypeHandler<E> {

	private final Class<E> type;

	public CodeEnumTypeHandler(Class<E> type) {
		this.type = type;
	}

	@Override
	public void setNonNullParameter(PreparedStatement ps, int i, E parameter, JdbcType jdbcType) throws SQLException {
		ps.setString(i, parameter.code());
	}

	@Override
	public E getNullableResult(ResultSet rs, String columnName) throws SQLException {
		return fromCode(rs.getString(columnName));
	}

	@Override
	public E getNullableResult(ResultSet rs, int columnIndex) throws SQLException {
		return fromCode(rs.getString(columnIndex));
	}

	@Override
	public E getNullableResult(CallableStatement cs, int columnIndex) throws SQLException {
		return fromCode(cs.getString(columnIndex));
	}

	private E fromCode(String code) {
		if (code == null) {
			return null;
		}
		String trimmed = code.trim();
		for (E e : type.getEnumConstants()) {
			if (e.code().equalsIgnoreCase(trimmed)) {
				return e;
			}
		}
		throw new IllegalArgumentException("未知状态码 '" + trimmed + "'，期望类型: " + type.getSimpleName());
	}
}
