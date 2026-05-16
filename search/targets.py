"""Curated demo targets y. Kept short so the local model θ can be run many times fast.

Good demo targets are texts the model has internalized: a very short prompt can
regenerate them via θ's own knowledge (the left / extreme-compression end), while
the identity prompt p = y is always the trivial right end.
"""

TARGETS = {
    "borges": {
        "label": "a paragraph on Borges’ “The Library of Babel”",
        "text": (
            "The Library of Babel contains every possible book: every arrangement "
            "of the twenty-five orthographic symbols across four hundred and ten "
            "pages. Somewhere on its hexagonal shelves sits the true catalogue, the "
            "refutation of that catalogue, and the proof of the falsity of the true "
            "catalogue. The library is total, and total libraries are useless: "
            "meaning is not in the shelves but in the call number that finds them."
        ),
    },
    "dickens": {
        "label": "the opening of Dickens’ “A Tale of Two Cities”",
        "text": (
            "It was the best of times, it was the worst of times, it was the age "
            "of wisdom, it was the age of foolishness, it was the epoch of belief, "
            "it was the epoch of incredulity, it was the season of Light, it was "
            "the season of Darkness, it was the spring of hope, it was the winter "
            "of despair."
        ),
    },
    "gettysburg": {
        "label": "the opening of Lincoln’s Gettysburg Address",
        "text": (
            "Four score and seven years ago our fathers brought forth on this "
            "continent, a new nation, conceived in Liberty, and dedicated to the "
            "proposition that all men are created equal."
        ),
    },
    "genesis": {
        "label": "the opening of Genesis (King James Bible)",
        "text": (
            "In the beginning God created the heaven and the earth. And the earth "
            "was without form, and void; and darkness was upon the face of the "
            "deep. And the Spirit of God moved upon the face of the waters."
        ),
    },
    "hamlet": {
        "label": "the opening of Hamlet’s soliloquy",
        "text": (
            "To be, or not to be, that is the question: Whether 'tis nobler in "
            "the mind to suffer the slings and arrows of outrageous fortune, or "
            "to take arms against a sea of troubles, and by opposing end them."
        ),
    },
}
