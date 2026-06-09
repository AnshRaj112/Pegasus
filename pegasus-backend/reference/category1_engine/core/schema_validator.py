# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-08T10:46:43Z
# --- END GENERATED FILE METADATA ---

"""Schema validation between source and target datasets."""

from category1.core.canonicalization import CanonicalizationEngine
from category1.models.schemas import (
    ColumnSchema,
    DatasetSchema,
    SchemaDifference,
    SchemaValidationResult,
)


class SchemaValidator:
    """Compares source and target schemas without touching data."""

    def __init__(self, column_mapping: dict[str, str] | None = None):
        self.column_mapping = column_mapping or {}
        self.canonicalizer = CanonicalizationEngine()

    def validate(
        self,
        source_schema: DatasetSchema,
        target_schema: DatasetSchema,
    ) -> SchemaValidationResult:
        differences: list[SchemaDifference] = []

        source_cols = {c.name: c for c in source_schema.columns}
        target_cols = {c.name: c for c in target_schema.columns}

        mapped_source_names = set()
        for src_name, tgt_name in self.column_mapping.items():
            mapped_source_names.add(src_name)
            if tgt_name not in target_cols:
                differences.append(SchemaDifference(
                    column=src_name,
                    difference_type="missing_target_column",
                    source_value=src_name,
                    target_value=None,
                ))
                continue
            if src_name in source_cols:
                self._compare_columns(source_cols[src_name], target_cols[tgt_name], differences)

        for name, col in source_cols.items():
            if name in mapped_source_names:
                continue
            if name not in target_cols:
                differences.append(SchemaDifference(
                    column=name,
                    difference_type="missing_in_target",
                    source_value=name,
                ))
            else:
                self._compare_columns(col, target_cols[name], differences)

        for name in target_cols:
            if name not in source_cols and name not in self.column_mapping.values():
                mapped_from = [k for k, v in self.column_mapping.items() if v == name]
                if not mapped_from:
                    differences.append(SchemaDifference(
                        column=name,
                        difference_type="extra_in_target",
                        target_value=name,
                    ))

        return SchemaValidationResult(is_valid=len(differences) == 0, differences=differences)

    def _compare_columns(
        self,
        source: ColumnSchema,
        target: ColumnSchema,
        differences: list[SchemaDifference],
    ) -> None:
        src_type, tgt_type = CanonicalizationEngine.harmonize_type(
            source.data_type, target.data_type
        )
        if src_type != tgt_type:
            differences.append(SchemaDifference(
                column=source.name,
                difference_type="type_mismatch",
                source_value=source.data_type,
                target_value=target.data_type,
            ))
        if source.nullable != target.nullable:
            differences.append(SchemaDifference(
                column=source.name,
                difference_type="nullable_mismatch",
                source_value=str(source.nullable),
                target_value=str(target.nullable),
            ))
        if source.precision and target.precision and source.precision != target.precision:
            differences.append(SchemaDifference(
                column=source.name,
                difference_type="precision_mismatch",
                source_value=str(source.precision),
                target_value=str(target.precision),
            ))
        if source.scale is not None and target.scale is not None and source.scale != target.scale:
            differences.append(SchemaDifference(
                column=source.name,
                difference_type="scale_mismatch",
                source_value=str(source.scale),
                target_value=str(target.scale),
            ))
