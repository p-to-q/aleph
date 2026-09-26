import Std
import BoundedCoordinate.GeneratedProblem

namespace BoundedCoordinate

def coordinatesOfLength : Nat → List (List Token)
  | 0 => [[]]
  | n + 1 => alphabet.flatMap fun token =>
      (coordinatesOfLength n).map fun suffix => token :: suffix

def coordinatesUpTo (bound : Nat) : List (List Token) :=
  (List.range (bound + 1)).flatMap coordinatesOfLength

theorem token_mem_alphabet (token : Token) : token ∈ alphabet := by
  cases token <;> simp [alphabet]

theorem coordinate_mem_coordinatesOfLength (coordinate : List Token) :
    coordinate ∈ coordinatesOfLength coordinate.length := by
  induction coordinate with
  | nil => simp [coordinatesOfLength]
  | cons head tail ih =>
      simp [coordinatesOfLength, token_mem_alphabet, ih]

theorem coordinate_mem_coordinatesUpTo_of_length_le
    (coordinate : List Token)
    {bound : Nat}
    (h : coordinate.length ≤ bound) :
    coordinate ∈ coordinatesUpTo bound := by
  apply List.mem_flatMap.mpr
  exact ⟨coordinate.length, List.mem_range.mpr (Nat.lt_succ_of_le h),
    coordinate_mem_coordinatesOfLength coordinate⟩

theorem witness_has_length_four : witness.length = 4 := by
  decide

theorem compositional_witness_reconstructs : compositionalDecode witness = target := by
  decide

theorem opaque_witness_reconstructs : opaqueDecode witness = target := by
  decide

private theorem compositional_enumeration_has_no_shorter_witness :
    ∀ coordinate ∈ coordinatesUpTo 3, compositionalDecode coordinate ≠ target := by
  decide

private theorem opaque_enumeration_has_no_shorter_witness :
    ∀ coordinate ∈ coordinatesUpTo 3, opaqueDecode coordinate ≠ target := by
  decide

private theorem compositional_enumeration_has_unique_bounded_witness :
    ∀ coordinate ∈ coordinatesUpTo 4,
      compositionalDecode coordinate = target → coordinate = witness := by
  set_option maxRecDepth 100000 in
    decide

private theorem opaque_enumeration_has_unique_bounded_witness :
    ∀ coordinate ∈ coordinatesUpTo 4,
      opaqueDecode coordinate = target → coordinate = witness := by
  set_option maxRecDepth 100000 in
    decide

theorem compositional_has_no_witness_of_length_le_three
    (coordinate : List Token)
    (h : coordinate.length ≤ 3) :
    compositionalDecode coordinate ≠ target :=
  compositional_enumeration_has_no_shorter_witness coordinate
    (coordinate_mem_coordinatesUpTo_of_length_le coordinate h)

theorem opaque_has_no_witness_of_length_le_three
    (coordinate : List Token)
    (h : coordinate.length ≤ 3) :
    opaqueDecode coordinate ≠ target :=
  opaque_enumeration_has_no_shorter_witness coordinate
    (coordinate_mem_coordinatesUpTo_of_length_le coordinate h)

theorem compositional_bounded_witness_is_unique
    (coordinate : List Token)
    (hLength : coordinate.length ≤ 4)
    (hDecode : compositionalDecode coordinate = target) :
    coordinate = witness :=
  compositional_enumeration_has_unique_bounded_witness coordinate
    (coordinate_mem_coordinatesUpTo_of_length_le coordinate hLength) hDecode

theorem opaque_bounded_witness_is_unique
    (coordinate : List Token)
    (hLength : coordinate.length ≤ 4)
    (hDecode : opaqueDecode coordinate = target) :
    coordinate = witness :=
  opaque_enumeration_has_unique_bounded_witness coordinate
    (coordinate_mem_coordinatesUpTo_of_length_le coordinate hLength) hDecode

end BoundedCoordinate
