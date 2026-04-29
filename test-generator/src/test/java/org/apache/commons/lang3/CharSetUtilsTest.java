package org.apache.commons.lang3;

import static org.junit.Assert.*;
import org.junit.Test;

public class CharSetUtilsTest {

    @Test
    public void testContainsAny_nullInputString() {
        assertFalse(CharSetUtils.containsAny(null, "abc"));
    }

    @Test
    public void testContainsAny_emptyInputString() {
        assertFalse(CharSetUtils.containsAny("", "abc"));
    }

    @Test
    public void testContainsAny_nullInputSet() {
        assertFalse(CharSetUtils.containsAny("abc", (String[]) null));
    }

    @Test
    public void testContainsAny_emptyInputSet() {
        assertFalse(CharSetUtils.containsAny("abc", ""));
    }

    @Test
    public void testContainsAny_standardCase() {
        assertTrue(CharSetUtils.containsAny("hello", "k-p"));
    }

    @Test
    public void testContainsAny_noMatchCase() {
        assertFalse(CharSetUtils.containsAny("hello", "a-d"));
    }

    @Test
    public void testCount_nullInputString() {
        assertEquals(0, CharSetUtils.count(null, "abc"));
    }

    @Test
    public void testCount_emptyInputString() {
        assertEquals(0, CharSetUtils.count("", "abc"));
    }

    @Test
    public void testCount_nullInputSet() {
        assertEquals(0, CharSetUtils.count("abc", (String[]) null));
    }

    @Test
    public void testCount_emptyInputSet() {
        assertEquals(0, CharSetUtils.count("abc", ""));
    }

    @Test
    public void testCount_standardCase() {
        assertEquals(3, CharSetUtils.count("hello", "k-p"));
    }

    @Test
    public void testCount_noMatchCase() {
        assertEquals(1, CharSetUtils.count("hello", "a-e"));
    }

    @Test
    public void testDelete_nullInputString() {
        assertNull(CharSetUtils.delete(null, "abc"));
    }

    @Test
    public void testDelete_emptyInputString() {
        assertEquals("", CharSetUtils.delete("", "abc"));
    }

    @Test
    public void testDelete_nullInputSet() {
        assertEquals("hello", CharSetUtils.delete("hello", (String[]) null));
    }

    @Test
    public void testDelete_emptyInputSet() {
        assertEquals("hello", CharSetUtils.delete("hello", ""));
    }

    @Test
    public void testDelete_standardCase() {
        assertEquals("eo", CharSetUtils.delete("hello", "hl"));
    }

    @Test
    public void testDelete_noMatchCase() {
        assertEquals("ho", CharSetUtils.delete("hello", "le"));
    }

    @Test
    public void testKeep_nullInputString() {
        assertNull(CharSetUtils.keep(null, "abc"));
    }

    @Test
    public void testKeep_emptyInputString() {
        assertEquals("", CharSetUtils.keep("", "abc"));
    }

    @Test
    public void testKeep_nullInputSet() {
        assertEquals("", CharSetUtils.keep("hello", (String[]) null));
    }

    @Test
    public void testKeep_emptyInputSet() {
        assertEquals("", CharSetUtils.keep("hello", ""));
    }

    @Test
    public void testKeep_standardCase() {
        assertEquals("hll", CharSetUtils.keep("hello", "hl"));
    }

    @Test
    public void testKeep_noMatchCase() {
        assertEquals("ell", CharSetUtils.keep("hello", "le"));
    }

    @Test
    public void testSqueeze_nullInputString() {
        assertNull(CharSetUtils.squeeze(null, "abc"));
    }

    @Test
    public void testSqueeze_emptyInputString() {
        assertEquals("", CharSetUtils.squeeze("", "abc"));
    }

    @Test
    public void testSqueeze_nullInputSet() {
        assertEquals("hello", CharSetUtils.squeeze("hello", (String[]) null));
    }

    @Test
    public void testSqueeze_emptyInputSet() {
        assertEquals("hello", CharSetUtils.squeeze("hello", ""));
    }

    @Test
    public void testSqueeze_standardCase() {
        assertEquals("helo", CharSetUtils.squeeze("hello", "k-p"));
    }

    @Test
    public void testSqueeze_noMatchCase() {
        assertEquals("hello", CharSetUtils.squeeze("hello", "a-e"));
    }
}