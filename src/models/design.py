"""Canonical object model for an elaborated RTL design.

These types are the parser's output contract: everything downstream (graph
builder, retrieval engine, API) consumes only these Pydantic models, never
raw Verilator AST dicts. This keeps the layers independent, per the
architecture requirement that parser / graph / retrieval / api stay decoupled.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Direction = Literal["INPUT", "OUTPUT", "INOUT", "NONE"]
SignalKind = Literal["wire", "register", "port", "parameter"]
AssignmentKind = Literal["continuous", "blocking", "nonblocking"]
AlwaysKind = Literal["combinational", "sequential", "latch", "initial"]
EdgeType = Literal["POS", "NEG", "BOTH", "NONE"]


class SourceLoc(BaseModel):
    file: str | None = None
    line: int | None = None
    col: int | None = None

    def __str__(self) -> str:  # pragma: no cover - convenience only
        if not self.file:
            return "<unknown>"
        return f"{self.file}:{self.line}:{self.col}"


class Parameter(BaseModel):
    id: str
    name: str
    module: str
    value_text: str | None = None
    dtype: str | None = None
    is_gparam: bool = False
    loc: SourceLoc | None = None


class Port(BaseModel):
    id: str
    name: str
    module: str
    direction: Direction
    width: int | None = None
    dtype: str | None = None
    loc: SourceLoc | None = None


class Signal(BaseModel):
    """A net/wire that is neither a port nor a clocked register."""

    id: str
    name: str
    module: str
    kind: SignalKind = "wire"
    width: int | None = None
    dtype: str | None = None
    loc: SourceLoc | None = None


class Register(BaseModel):
    """A signal driven by a nonblocking assignment inside a clocked always block."""

    id: str
    name: str
    module: str
    width: int | None = None
    dtype: str | None = None
    clock: str | None = None
    clock_edge: EdgeType | None = None
    reset: str | None = None
    reset_edge: EdgeType | None = None
    loc: SourceLoc | None = None


class Expression(BaseModel):
    """A rendered RHS/condition expression tied to an assignment or always block."""

    id: str
    module: str
    text: str
    reads: list[str] = Field(default_factory=list)
    loc: SourceLoc | None = None


class Assignment(BaseModel):
    id: str
    module: str
    kind: AssignmentKind
    lhs: list[str] = Field(default_factory=list)
    reads: list[str] = Field(default_factory=list)
    expression_id: str | None = None
    always_block_id: str | None = None
    loc: SourceLoc | None = None


class SensitivityItem(BaseModel):
    edge: EdgeType
    signal: str


class AlwaysBlock(BaseModel):
    id: str
    module: str
    kind: AlwaysKind
    sensitivity: list[SensitivityItem] = Field(default_factory=list)
    clock: str | None = None
    clock_edge: EdgeType | None = None
    reset: str | None = None
    reset_edge: EdgeType | None = None
    reads: list[str] = Field(default_factory=list)
    writes: list[str] = Field(default_factory=list)
    assignment_ids: list[str] = Field(default_factory=list)
    loc: SourceLoc | None = None


class PinConnection(BaseModel):
    port_name: str
    expr_text: str
    reads: list[str] = Field(default_factory=list)


class Instance(BaseModel):
    id: str
    name: str
    parent_module: str
    module_type: str
    pins: list[PinConnection] = Field(default_factory=list)
    loc: SourceLoc | None = None


class ClockDomain(BaseModel):
    id: str
    name: str


class ResetDomain(BaseModel):
    id: str
    name: str
    edge: EdgeType = "NONE"


class Module(BaseModel):
    name: str
    orig_name: str
    level: int = 0
    is_top: bool = False
    parameters: list[Parameter] = Field(default_factory=list)
    ports: list[Port] = Field(default_factory=list)
    signals: list[Signal] = Field(default_factory=list)
    registers: list[Register] = Field(default_factory=list)
    instances: list[Instance] = Field(default_factory=list)
    always_blocks: list[AlwaysBlock] = Field(default_factory=list)
    assignments: list[Assignment] = Field(default_factory=list)
    expressions: list[Expression] = Field(default_factory=list)


class Design(BaseModel):
    """Full canonical model for one elaborated design."""

    top_module: str | None = None
    modules: dict[str, Module] = Field(default_factory=dict)
    clock_domains: dict[str, ClockDomain] = Field(default_factory=dict)
    reset_domains: dict[str, ResetDomain] = Field(default_factory=dict)
    source_files: dict[str, str] = Field(default_factory=dict)
