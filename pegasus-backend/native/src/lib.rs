//! Fast multichar delimiter line splitting with inline canonicalize → hash → partition → spill.

// --- BEGIN GENERATED FILE METADATA ---
// Authors: Ansh Raj
// Last edited: 2026-06-16T11:17:59Z
// --- END GENERATED FILE METADATA ---

use std::collections::HashMap;
use std::fs::{self, File};
use std::io::{self, Write};
use std::path::PathBuf;

use memchr::memchr;
use memmap2::Mmap;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};
use xxhash_rust::xxh64::Xxh64;

const FIELD_SEP: u8 = 0x1f;
const IO_BLOCK: usize = 16 * 1024 * 1024;
const FLUSH_THRESHOLD: usize = 256 * 1024;
const DRILLDOWN_BUF_BYTES: usize = 8 * 1024 * 1024;

fn write_u16_be(writer: &mut impl Write, value: usize) -> io::Result<()> {
    if value > 0xffff {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "drilldown field exceeds 65535 bytes",
        ));
    }
    writer.write_all(&(value as u16).to_be_bytes())
}

struct DrilldownWriter {
    writer: io::BufWriter<File>,
}

impl DrilldownWriter {
    fn create(path: PathBuf) -> PyResult<Self> {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).map_err(|e| PyValueError::new_err(e.to_string()))?;
        }
        let file = File::create(&path).map_err(|e| {
            PyValueError::new_err(format!("create drilldown file {path:?}: {e}"))
        })?;
        Ok(Self {
            writer: io::BufWriter::with_capacity(DRILLDOWN_BUF_BYTES, file),
        })
    }

    fn write_row(&mut self, identity: &str, values: &[String]) -> io::Result<()> {
        let ident_b = identity.as_bytes();
        write_u16_be(&mut self.writer, ident_b.len())?;
        self.writer.write_all(ident_b)?;
        for value in values {
            let val_b = value.as_bytes();
            write_u16_be(&mut self.writer, val_b.len())?;
            self.writer.write_all(val_b)?;
        }
        Ok(())
    }

    fn flush(&mut self) -> io::Result<()> {
        self.writer.flush()
    }
}

#[pyfunction]
fn extension_available() -> bool {
    true
}

fn canonical_field(raw: &str) -> String {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return "__NULL__".to_string();
    }
    let lower = trimmed.to_ascii_lowercase();
    if matches!(lower.as_str(), "null" | "none" | "na" | "n/a") {
        return "__NULL__".to_string();
    }
    trimmed.to_string()
}

fn is_nullish_ascii(s: &str) -> bool {
    matches!(
        s.as_bytes(),
        b"null" | b"none" | b"na" | b"n/a" | b"NULL" | b"NONE" | b"NA" | b"N/A"
    ) || {
        let lower = s.to_ascii_lowercase();
        matches!(lower.as_str(), "null" | "none" | "na" | "n/a")
    }
}

fn canonical_field_bytes(raw: &[u8]) -> String {
    let trimmed = std::str::from_utf8(raw)
        .map(str::trim)
        .unwrap_or("");
    if trimmed.is_empty() {
        return "__NULL__".to_string();
    }
    if is_nullish_ascii(trimmed) {
        return "__NULL__".to_string();
    }
    trimmed.to_string()
}

fn fingerprint_from_canon_parts(parts: &[String]) -> u64 {
    if parts.is_empty() {
        return 0;
    }
    let mut hasher = Xxh64::new(0);
    for (idx, part) in parts.iter().enumerate() {
        if idx > 0 {
            hasher.update(&[FIELD_SEP]);
        }
        hasher.update(part.as_bytes());
    }
    hasher.digest()
}

fn fingerprint_fields(fields: &[&[u8]], compare_idxs: &[usize]) -> u64 {
    if compare_idxs.is_empty() {
        return 0;
    }
    let mut hasher = Xxh64::new(0);
    let mut canon = String::new();
    for (idx, &col_idx) in compare_idxs.iter().enumerate() {
        if idx > 0 {
            hasher.update(&[FIELD_SEP]);
        }
        let raw = fields.get(col_idx).copied().unwrap_or(b"");
        canon = canonical_field_bytes(raw);
        hasher.update(canon.as_bytes());
    }
    hasher.digest()
}

fn partition_from_identity(identity: &str, num_partitions: u32) -> u32 {
    if num_partitions == 0 {
        return 0;
    }
    let mut hasher = Xxh64::new(0);
    hasher.update(identity.as_bytes());
    (hasher.digest() % u64::from(num_partitions)) as u32
}

fn row_xor_digest(identity: &str, fp_hash: u64) -> u64 {
    let mut payload = String::with_capacity(identity.len() + 24);
    payload.push_str(identity);
    payload.push('\x1f');
    payload.push_str(&fp_hash.to_string());
    let mut hasher = Xxh64::new(0);
    hasher.update(payload.as_bytes());
    hasher.digest()
}

fn split_delim<'a>(line: &'a [u8], delim: &[u8]) -> Vec<&'a [u8]> {
    if delim.is_empty() {
        return vec![line];
    }
    let mut out = Vec::new();
    let mut start = 0usize;
    let mut i = 0usize;
    while i + delim.len() <= line.len() {
        if &line[i..i + delim.len()] == delim {
            out.push(&line[start..i]);
            i += delim.len();
            start = i;
        } else {
            i += 1;
        }
    }
    out.push(&line[start..]);
    out
}

fn strip_cr(line: &[u8]) -> &[u8] {
    if line.ends_with(b"\r") {
        &line[..line.len() - 1]
    } else {
        line
    }
}

struct ColumnMap {
    identity_idxs: Vec<usize>,
    compare_idxs: Vec<usize>,
}

impl ColumnMap {
    fn from_headers(
        headers: Vec<String>,
        identity_cols: &[String],
        compare_cols: &[String],
    ) -> PyResult<Self> {
        let mut identity_idxs = Vec::with_capacity(identity_cols.len());
        for name in identity_cols {
            let idx = headers
                .iter()
                .position(|h| h == name)
                .ok_or_else(|| PyValueError::new_err(format!("identity column not found: {name}")))?;
            identity_idxs.push(idx);
        }
        let mut compare_idxs = Vec::with_capacity(compare_cols.len());
        for name in compare_cols {
            let idx = headers
                .iter()
                .position(|h| h == name)
                .ok_or_else(|| PyValueError::new_err(format!("compare column not found: {name}")))?;
            compare_idxs.push(idx);
        }
        Ok(Self {
            identity_idxs,
            compare_idxs,
        })
    }
}

struct SpillChunk {
    partitions: HashMap<u32, (Vec<String>, Vec<u64>)>,
    rows: usize,
}

struct LineSpiller {
    delim: Vec<u8>,
    columns: Option<ColumnMap>,
    chunk_rows: usize,
    num_partitions: u32,
    skipped: usize,
    skip_rows: usize,
    has_header: bool,
    pending: Vec<u8>,
    line_buf_rows: usize,
    partitions: HashMap<u32, (Vec<String>, Vec<u64>)>,
    identity_cols: Vec<String>,
    compare_cols: Vec<String>,
    drilldown: Option<DrilldownWriter>,
    finished: bool,
}

impl LineSpiller {
    fn new(
        delim: Vec<u8>,
        has_header: bool,
        skip_rows: usize,
        chunk_rows: usize,
        num_partitions: u32,
        identity_cols: Vec<String>,
        compare_cols: Vec<String>,
        drilldown: Option<DrilldownWriter>,
    ) -> Self {
        Self {
            delim,
            columns: None,
            chunk_rows: chunk_rows.max(1),
            num_partitions,
            skipped: 0,
            skip_rows,
            has_header,
            pending: Vec::new(),
            line_buf_rows: 0,
            partitions: HashMap::new(),
            identity_cols,
            compare_cols,
            drilldown,
            finished: false,
        }
    }

    fn scan_lines(&mut self, data: &[u8]) -> PyResult<Vec<SpillChunk>> {
        let mut out = Vec::new();
        let mut start = 0usize;
        for i in 0..data.len() {
            if data[i] != b'\n' {
                continue;
            }
            let line = strip_cr(&data[start..i]);
            start = i + 1;
            if let Some(chunk) = self.process_line(line)? {
                out.push(chunk);
            }
        }
        if start < data.len() {
            self.pending.extend_from_slice(&data[start..]);
        }
        Ok(out)
    }

    fn feed(&mut self, data: &[u8]) -> PyResult<Vec<SpillChunk>> {
        if !self.pending.is_empty() {
            self.pending.extend_from_slice(data);
            let combined = std::mem::take(&mut self.pending);
            return self.scan_lines(&combined);
        }
        self.scan_lines(data)
    }

    fn drain_pending(&mut self) -> PyResult<Option<SpillChunk>> {
        if self.finished {
            return Ok(None);
        }
        self.finished = true;
        if !self.pending.is_empty() {
            let tail = std::mem::take(&mut self.pending);
            let line = strip_cr(&tail);
            if !line.is_empty() {
                if let Some(chunk) = self.process_line(line)? {
                    return Ok(Some(chunk));
                }
            }
        }
        if self.line_buf_rows > 0 {
            return Ok(Some(self.flush_chunk()));
        }
        Ok(None)
    }

    fn process_line(&mut self, line: &[u8]) -> PyResult<Option<SpillChunk>> {
        if line.is_empty() {
            return Ok(None);
        }
        if self.columns.is_none() {
            if self.skipped < self.skip_rows {
                self.skipped += 1;
                return Ok(None);
            }
            let fields = split_delim(line, &self.delim);
            if self.has_header {
                let headers: Vec<String> = fields
                    .iter()
                    .map(|f| String::from_utf8_lossy(f).into_owned())
                    .collect();
                self.columns = Some(ColumnMap::from_headers(
                    headers,
                    &self.identity_cols,
                    &self.compare_cols,
                )?);
                return Ok(None);
            }
            let col_count = fields.len().max(1);
            let headers: Vec<String> = (0..col_count).map(|i| format!("col_{i}")).collect();
            self.columns = Some(ColumnMap::from_headers(
                headers,
                &self.identity_cols,
                &self.compare_cols,
            )?);
            self.ingest_data_line(line)?;
            return self.maybe_emit();
        }
        self.ingest_data_line(line)?;
        self.maybe_emit()
    }

    fn ingest_data_line(&mut self, line: &[u8]) -> PyResult<()> {
        let columns = self
            .columns
            .as_ref()
            .ok_or_else(|| PyValueError::new_err("headers not resolved"))?;
        let fields = split_delim(line, &self.delim);
        let mut identity = String::new();
        for (idx, &col_idx) in columns.identity_idxs.iter().enumerate() {
            if idx > 0 {
                identity.push('|');
            }
            let raw = fields.get(col_idx).copied().unwrap_or(b"");
            identity.push_str(&canonical_field_bytes(raw));
        }
        let mut compare_values: Vec<String> = Vec::with_capacity(columns.compare_idxs.len());
        for &col_idx in &columns.compare_idxs {
            let raw = fields.get(col_idx).copied().unwrap_or(b"");
            compare_values.push(canonical_field_bytes(raw));
        }
        if let Some(writer) = self.drilldown.as_mut() {
            writer
                .write_row(&identity, &compare_values)
                .map_err(|e| PyValueError::new_err(e.to_string()))?;
        }
        let fp = fingerprint_from_canon_parts(&compare_values);
        let pid = partition_from_identity(&identity, self.num_partitions);
        let entry = self
            .partitions
            .entry(pid)
            .or_insert_with(|| (Vec::new(), Vec::new()));
        entry.0.push(identity);
        entry.1.push(fp);
        self.line_buf_rows += 1;
        Ok(())
    }

    fn maybe_emit(&mut self) -> PyResult<Option<SpillChunk>> {
        if self.line_buf_rows >= self.chunk_rows {
            return Ok(Some(self.flush_chunk()));
        }
        Ok(None)
    }

    fn flush_chunk(&mut self) -> SpillChunk {
        let rows = self.line_buf_rows;
        self.line_buf_rows = 0;
        SpillChunk {
            partitions: std::mem::take(&mut self.partitions),
            rows,
        }
    }
}

fn encode_cbl2_partition(identities: &[String], hashes: &[u64]) -> PyResult<Vec<u8>> {
    let n = identities.len();
    if n != hashes.len() {
        return Err(PyValueError::new_err("identity/hash length mismatch"));
    }
    let mut buf = Vec::with_capacity(8 + n * 24);
    buf.extend_from_slice(b"CBL2");
    buf.extend_from_slice(&(n as u32).to_be_bytes());
    for ident in identities {
        let key_b = ident.as_bytes();
        if key_b.len() > 65535 {
            return Err(PyValueError::new_err("identity key exceeds 65535 bytes"));
        }
        buf.extend_from_slice(&(key_b.len() as u16).to_be_bytes());
        buf.extend_from_slice(key_b);
    }
    for &fp in hashes {
        buf.extend_from_slice(&fp.to_be_bytes());
    }
    Ok(buf)
}

struct NativeSpillWriter {
    base: PathBuf,
    buffers: HashMap<u32, Vec<u8>>,
    merkle_xor: HashMap<u32, u64>,
    row_count: usize,
    track_merkle: bool,
}

impl NativeSpillWriter {
    fn new(base: PathBuf, track_merkle: bool) -> PyResult<Self> {
        fs::create_dir_all(&base).map_err(|e| PyValueError::new_err(e.to_string()))?;
        Ok(Self {
            base,
            buffers: HashMap::new(),
            merkle_xor: HashMap::new(),
            row_count: 0,
            track_merkle,
        })
    }

    fn absorb_chunk(&mut self, chunk: SpillChunk) -> PyResult<()> {
        self.row_count += chunk.rows;
        for (pid, (idents, fps)) in chunk.partitions {
            if self.track_merkle {
                let acc = self.merkle_xor.entry(pid).or_insert(0);
                for (identity, fp) in idents.iter().zip(fps.iter()) {
                    *acc ^= row_xor_digest(identity, *fp);
                }
            }
            let block = encode_cbl2_partition(&idents, &fps)?;
            self.write_block(pid, &block)?;
        }
        Ok(())
    }

    fn write_block(&mut self, pid: u32, block: &[u8]) -> io::Result<()> {
        let buf = self.buffers.entry(pid).or_insert_with(Vec::new);
        buf.extend_from_slice(block);
        if buf.len() >= FLUSH_THRESHOLD {
            self.flush(pid)?;
        }
        Ok(())
    }

    fn flush(&mut self, pid: u32) -> io::Result<()> {
        let Some(buf) = self.buffers.get_mut(&pid) else {
            return Ok(());
        };
        if buf.is_empty() {
            return Ok(());
        }
        let path = self.base.join(format!("part_{pid:05}.bin"));
        let mut file = fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&path)
            .map_err(|e| io::Error::new(e.kind(), format!("open spill partition {path:?}: {e}")))?;
        file.write_all(buf)?;
        buf.clear();
        file.flush()?;
        Ok(())
    }

    fn close(mut self) -> PyResult<(usize, HashMap<u32, u64>)> {
        for pid in self.buffers.keys().copied().collect::<Vec<_>>() {
            self.flush(pid).map_err(|e| PyValueError::new_err(e.to_string()))?;
        }
        Ok((self.row_count, self.merkle_xor))
    }
}

struct SpillConfig {
    delim: Vec<u8>,
    has_header: bool,
    skip_rows: usize,
    chunk_rows: usize,
    num_partitions: u32,
    identity_cols: Vec<String>,
    compare_cols: Vec<String>,
    track_merkle: bool,
    drilldown_path: Option<PathBuf>,
}

fn make_line_spiller(cfg: &SpillConfig) -> PyResult<LineSpiller> {
    let drilldown = if let Some(path) = cfg.drilldown_path.clone() {
        Some(DrilldownWriter::create(path)?)
    } else {
        None
    };
    Ok(LineSpiller::new(
        cfg.delim.clone(),
        cfg.has_header,
        cfg.skip_rows,
        cfg.chunk_rows,
        cfg.num_partitions,
        cfg.identity_cols.clone(),
        cfg.compare_cols.clone(),
        drilldown,
    ))
}

fn finish_line_spiller(mut spiller: LineSpiller) -> PyResult<()> {
    if let Some(mut writer) = spiller.drilldown.take() {
        writer
            .flush()
            .map_err(|e| PyValueError::new_err(e.to_string()))?;
    }
    Ok(())
}

fn spill_from_reader(
    mut read_block: impl FnMut(usize) -> PyResult<Vec<u8>>,
    output_dir: &str,
    cfg: SpillConfig,
    block_size: usize,
) -> PyResult<(usize, HashMap<u32, u64>)> {
    let mut spiller = make_line_spiller(&cfg)?;
    let mut writer = NativeSpillWriter::new(PathBuf::from(output_dir), cfg.track_merkle)?;
    loop {
        let data = read_block(block_size)?;
        if data.is_empty() {
            break;
        }
        for chunk in spiller.feed(&data)? {
            writer.absorb_chunk(chunk)?;
        }
    }
    if let Some(chunk) = spiller.drain_pending()? {
        writer.absorb_chunk(chunk)?;
    }
    finish_line_spiller(spiller)?;
    writer.close()
}

fn spill_result_to_py(
    py: Python<'_>,
    rows: usize,
    merkle_xor: HashMap<u32, u64>,
    drilldown_written: bool,
) -> PyResult<Py<PyDict>> {
    let dict = PyDict::new_bound(py);
    dict.set_item("rows", rows)?;
    let merkle = PyDict::new_bound(py);
    for (pid, xor) in merkle_xor {
        merkle.set_item(pid, xor)?;
    }
    dict.set_item("merkle_xor", merkle)?;
    dict.set_item("drilldown_written", drilldown_written)?;
    Ok(dict.unbind())
}

fn parse_drilldown_path(drilldown_path: Option<&str>) -> Option<PathBuf> {
    drilldown_path.and_then(|p| {
        let trimmed = p.trim();
        if trimmed.is_empty() {
            None
        } else {
            Some(PathBuf::from(trimmed))
        }
    })
}

#[pyfunction]
fn spill_mmap_file(
    py: Python<'_>,
    path: &str,
    output_dir: &str,
    delimiter: &str,
    has_header: bool,
    skip_rows: usize,
    chunk_rows: usize,
    identity_columns: Vec<String>,
    compare_columns: Vec<String>,
    num_partitions: u32,
    track_merkle: bool,
    drilldown_path: Option<&str>,
) -> PyResult<Py<PyDict>> {
    let path_owned = path.to_string();
    let output_owned = output_dir.to_string();
    let dd_path = parse_drilldown_path(drilldown_path);
    let cfg = SpillConfig {
        delim: delimiter.as_bytes().to_vec(),
        has_header,
        skip_rows,
        chunk_rows,
        num_partitions,
        identity_cols: identity_columns,
        compare_cols: compare_columns,
        track_merkle,
        drilldown_path: dd_path,
    };
    let drilldown_written = cfg.drilldown_path.is_some();
    let (rows, merkle_xor) = py.allow_threads(move || -> PyResult<(usize, HashMap<u32, u64>)> {
        let file = File::open(&path_owned).map_err(|e| PyValueError::new_err(e.to_string()))?;
        let mmap = unsafe { Mmap::map(&file).map_err(|e| PyValueError::new_err(e.to_string()))? };
        let mut spiller = make_line_spiller(&cfg)?;
        let mut writer = NativeSpillWriter::new(PathBuf::from(&output_owned), cfg.track_merkle)?;
        for chunk in spiller.scan_lines(&mmap)? {
            writer.absorb_chunk(chunk)?;
        }
        if let Some(chunk) = spiller.drain_pending()? {
            writer.absorb_chunk(chunk)?;
        }
        finish_line_spiller(spiller)?;
        writer.close()
    })?;
    spill_result_to_py(py, rows, merkle_xor, drilldown_written)
}

#[pyfunction]
fn spill_stream_file(
    py: Python<'_>,
    read_callable: Bound<'_, PyAny>,
    output_dir: &str,
    delimiter: &str,
    has_header: bool,
    skip_rows: usize,
    chunk_rows: usize,
    identity_columns: Vec<String>,
    compare_columns: Vec<String>,
    num_partitions: u32,
    track_merkle: bool,
    block_size: usize,
    drilldown_path: Option<&str>,
) -> PyResult<Py<PyDict>> {
    let read = read_callable.unbind();
    let block = block_size.max(64 * 1024);
    let dd_path = parse_drilldown_path(drilldown_path);
    let drilldown_written = dd_path.is_some();
    let cfg = SpillConfig {
        delim: delimiter.as_bytes().to_vec(),
        has_header,
        skip_rows,
        chunk_rows,
        num_partitions,
        identity_cols: identity_columns,
        compare_cols: compare_columns,
        track_merkle,
        drilldown_path: dd_path,
    };
    let (rows, merkle_xor) = spill_from_reader(
        |size| {
            let data: Vec<u8> = read.bind(py).call1((size,))?.extract()?;
            Ok(data)
        },
        output_dir,
        cfg,
        block,
    )?;
    spill_result_to_py(py, rows, merkle_xor, drilldown_written)
}

// --- Legacy chunk iterators (used by unit tests) ---

fn chunk_to_py(py: Python<'_>, chunk: SpillChunk) -> PyResult<Py<PyDict>> {
    let dict = PyDict::new_bound(py);
    dict.set_item("rows", chunk.rows)?;
    let parts = PyDict::new_bound(py);
    for (pid, (idents, fps)) in chunk.partitions {
        let block = encode_cbl2_partition(&idents, &fps)?;
        parts.set_item(pid, PyBytes::new_bound(py, &block))?;
    }
    dict.set_item("partitions", parts)?;
    Ok(dict.unbind())
}

#[pyclass]
struct MmapSpillIter {
    mmap: Option<Mmap>,
    offset: usize,
    spiller: LineSpiller,
    pending_chunks: Vec<SpillChunk>,
    drained: bool,
}

#[pymethods]
impl MmapSpillIter {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(mut slf: PyRefMut<'_, Self>) -> PyResult<Option<Py<PyDict>>> {
        loop {
            if let Some(chunk) = slf.pending_chunks.pop() {
                return Ok(Some(chunk_to_py(slf.py(), chunk)?));
            }
            if let Some(mmap_len) = slf.mmap.as_ref().map(|m| m.len()) {
                if slf.offset < mmap_len {
                    let block = {
                        let mmap = slf.mmap.as_ref().unwrap();
                        let start = slf.offset;
                        let end = (start + IO_BLOCK).min(mmap.len());
                        let slice = mmap[start..end].to_vec();
                        slf.offset = end;
                        slice
                    };
                    for chunk in slf.spiller.feed(&block)? {
                        slf.pending_chunks.push(chunk);
                    }
                    if let Some(chunk) = slf.pending_chunks.pop() {
                        return Ok(Some(chunk_to_py(slf.py(), chunk)?));
                    }
                    continue;
                }
            }
            slf.mmap = None;
            if !slf.drained {
                slf.drained = true;
                if let Some(chunk) = slf.spiller.drain_pending()? {
                    return Ok(Some(chunk_to_py(slf.py(), chunk)?));
                }
            }
            return Ok(None);
        }
    }
}

#[pyfunction]
fn iter_mmap_spill_chunks(
    path: &str,
    delimiter: &str,
    has_header: bool,
    skip_rows: usize,
    chunk_rows: usize,
    identity_columns: Vec<String>,
    compare_columns: Vec<String>,
    num_partitions: u32,
) -> PyResult<MmapSpillIter> {
    let file = File::open(path).map_err(|e| PyValueError::new_err(e.to_string()))?;
    let mmap = unsafe { Mmap::map(&file).map_err(|e| PyValueError::new_err(e.to_string()))? };
    let spiller = LineSpiller::new(
        delimiter.as_bytes().to_vec(),
        has_header,
        skip_rows,
        chunk_rows,
        num_partitions,
        identity_columns,
        compare_columns,
        None,
    );
    Ok(MmapSpillIter {
        mmap: Some(mmap),
        offset: 0,
        spiller,
        pending_chunks: Vec::new(),
        drained: false,
    })
}

#[pyclass]
struct StreamSpillIter {
    read_callable: Py<PyAny>,
    block_size: usize,
    spiller: LineSpiller,
    pending_chunks: Vec<SpillChunk>,
    exhausted: bool,
    drained: bool,
}

#[pymethods]
impl StreamSpillIter {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(mut slf: PyRefMut<'_, Self>) -> PyResult<Option<Py<PyDict>>> {
        let py = slf.py();
        loop {
            if let Some(chunk) = slf.pending_chunks.pop() {
                return Ok(Some(chunk_to_py(py, chunk)?));
            }
            if !slf.exhausted {
                let read = slf.read_callable.bind(py);
                let block_py = read.call1((slf.block_size,))?;
                let data: Vec<u8> = block_py.extract()?;
                if data.is_empty() {
                    slf.exhausted = true;
                } else {
                    for chunk in slf.spiller.feed(&data)? {
                        slf.pending_chunks.push(chunk);
                    }
                    continue;
                }
            }
            if !slf.drained {
                slf.drained = true;
                if let Some(chunk) = slf.spiller.drain_pending()? {
                    return Ok(Some(chunk_to_py(py, chunk)?));
                }
            }
            return Ok(None);
        }
    }
}

#[pyfunction]
fn iter_stream_spill_chunks(
    read_callable: Bound<'_, PyAny>,
    delimiter: &str,
    has_header: bool,
    skip_rows: usize,
    chunk_rows: usize,
    identity_columns: Vec<String>,
    compare_columns: Vec<String>,
    num_partitions: u32,
    block_size: usize,
) -> PyResult<StreamSpillIter> {
    Ok(StreamSpillIter {
        read_callable: read_callable.unbind(),
        block_size: block_size.max(64 * 1024),
        spiller: LineSpiller::new(
            delimiter.as_bytes().to_vec(),
            has_header,
            skip_rows,
            chunk_rows,
            num_partitions,
            identity_columns,
            compare_columns,
            None,
        ),
        pending_chunks: Vec::new(),
        exhausted: false,
        drained: false,
    })
}

#[pymodule]
fn pegasus_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(extension_available, m)?)?;
    m.add_function(wrap_pyfunction!(spill_mmap_file, m)?)?;
    m.add_function(wrap_pyfunction!(spill_stream_file, m)?)?;
    m.add_function(wrap_pyfunction!(iter_mmap_spill_chunks, m)?)?;
    m.add_function(wrap_pyfunction!(iter_stream_spill_chunks, m)?)?;
    m.add_class::<MmapSpillIter>()?;
    m.add_class::<StreamSpillIter>()?;
    Ok(())
}
