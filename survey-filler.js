// ============================================================
// Survey Auto-Filler Script
// Course: COMPUTER AIDED PATTERNS DEVELOPMENT
// ============================================================
// Usage: Open browser console (F12) on the survey page and paste this script
// ============================================================

(function() {
    'use strict';

    // ---------------------
    // CONFIGURATION
    // ---------------------
    const GENDER_VALUE = null; // Set to "1" for Male or "2" for Female, leave null to choose manually
    const QUESTION_35_VALUE = "1"; // "you bought handout for this course" → False = "1"
    const GENERAL_COMMENT = "The lecturer demonstrated excellent knowledge of the subject matter and maintained a professional approach throughout the course. The teaching methods were effective and engaging, making complex concepts easier to understand. I would highly recommend this course to other students.";

    // ---------------------
    // HELPER FUNCTIONS
    // ---------------------

    // Set a <select> dropdown value and trigger change event
    function setSelectValue(name, value) {
        const select = document.querySelector(`select[name="${name}"]`);
        if (select) {
            select.value = value;
            select.dispatchEvent(new Event('change', { bubbles: true }));
            console.log(`✅ Set ${name} = ${value}`);
            return true;
        }
        console.warn(`⚠️ Select not found: ${name}`);
        return false;
    }

    // Set a radio button value and trigger change event
    function setRadioValue(name, value) {
        const radio = document.querySelector(`input[name="${name}"][value="${value}"]`);
        if (radio) {
            radio.checked = true;
            radio.dispatchEvent(new Event('change', { bubbles: true }));
            console.log(`✅ Set ${name} = ${value}`);
            return true;
        }
        console.warn(`⚠️ Radio not found: ${name} with value ${value}`);
        return false;
    }

    // Set a textarea value and trigger change event
    function setTextareaValue(name, value) {
        const textarea = document.querySelector(`textarea[name="${name}"]`);
        if (textarea) {
            textarea.value = value;
            textarea.dispatchEvent(new Event('change', { bubbles: true }));
            console.log(`✅ Set textarea ${name}`);
            return true;
        }
        console.warn(`⚠️ Textarea not found: ${name}`);
        return false;
    }

    // ---------------------
    // LIKERT SCALE MAPPING
    // ---------------------
    // Questions use answer type ID 4 (Likert Scale):
    //   1 = Strongly Disagree
    //   2 = Disagree
    //   3 = Neutral
    //   4 = Agree
    //   5 = Strongly Agree
    const STRONGLY_AGREE = "5";

    // ---------------------
    // FILL THE FORM
    // ---------------------

    console.log("🚀 Starting survey auto-fill...\n");

    // --- 1. GENDER (Question 1) ---
    if (GENDER_VALUE) {
        setSelectValue("57-155", GENDER_VALUE);
    } else {
        console.log("⏭️ Gender left for manual selection (Question 1)");
    }

    // --- 2. LECTURER'S BEARING (Questions 2-7) ---
    console.log("\n📋 Filling LECTURER'S BEARING...");
    setSelectValue("58-156", STRONGLY_AGREE); // Q2: Lecturer is punctual
    setSelectValue("58-157", STRONGLY_AGREE); // Q3: Lecturer is regular
    setSelectValue("58-158", STRONGLY_AGREE); // Q4: Lecturer dresses well
    setSelectValue("58-159", STRONGLY_AGREE); // Q5: Lecturer is approachable
    setSelectValue("58-160", STRONGLY_AGREE); // Q6: Lecturer's movement equitable
    setSelectValue("58-161", STRONGLY_AGREE); // Q7: Lecturer is audible

    // --- 3. PEDAGOGY (Questions 8-14) ---
    console.log("\n📋 Filling PEDAGOGY...");
    setSelectValue("59-162", STRONGLY_AGREE); // Q8: Follows course outline
    setSelectValue("59-163", STRONGLY_AGREE); // Q9: Covers content on schedule
    setSelectValue("59-164", STRONGLY_AGREE); // Q10: Knowledge of subject matter
    setSelectValue("59-165", STRONGLY_AGREE); // Q11: Sets lesson objectives
    setSelectValue("59-166", STRONGLY_AGREE); // Q12: Methods are effective
    setSelectValue("59-168", STRONGLY_AGREE); // Q13: Clear during teaching
    setSelectValue("59-169", STRONGLY_AGREE); // Q14: Uses LMS/Online teaching

    // --- 4. ANDRAGOGY (Questions 15-18) ---
    console.log("\n📋 Filling ANDRAGOGY...");
    setSelectValue("60-170", STRONGLY_AGREE); // Q15: Links lessons to practice
    setSelectValue("60-171", STRONGLY_AGREE); // Q16: Encourages participation
    setSelectValue("60-173", STRONGLY_AGREE); // Q17: Challenges students
    setSelectValue("60-174", STRONGLY_AGREE); // Q18: Influences to create new knowledge

    // --- 5. MOTIVATION (Questions 19-21) ---
    console.log("\n📋 Filling MOTIVATION...");
    setSelectValue("61-175", STRONGLY_AGREE); // Q19: Stimulates interest
    setSelectValue("61-176", STRONGLY_AGREE); // Q20: Respects students
    setSelectValue("61-177", STRONGLY_AGREE); // Q21: Has interest in students' learning

    // --- 6. ASSESSMENT AND EVALUATION (Questions 22-25) ---
    console.log("\n📋 Filling ASSESSMENT AND EVALUATION...");
    setSelectValue("62-178", STRONGLY_AGREE); // Q22: Monitors progress
    setSelectValue("62-179", STRONGLY_AGREE); // Q23: Gives assignments/quizzes
    setSelectValue("62-181", STRONGLY_AGREE); // Q24: Returns marked assignments
    setSelectValue("62-182", STRONGLY_AGREE); // Q25: Discusses marked assignments

    // --- 7. READING MATERIAL (Questions 26-28) ---
    console.log("\n📋 Filling READING MATERIAL...");
    setSelectValue("63-183", STRONGLY_AGREE); // Q26: Suggests extra reading
    setSelectValue("63-184", STRONGLY_AGREE); // Q27: Encourages library visits
    setSelectValue("63-185", STRONGLY_AGREE); // Q28: Gives internet links

    // --- 8. LEARNING ENVIRONMENT (Questions 29-33) ---
    const NEUTRAL = "3";
    console.log("\n📋 Filling LEARNING ENVIRONMENT...");
    setSelectValue("64-186", NEUTRAL); // Q29: Cleanliness
    setSelectValue("64-187", NEUTRAL); // Q30: Furniture organized
    setSelectValue("64-188", NEUTRAL); // Q31: Adequacy of furniture
    setSelectValue("64-189", NEUTRAL); // Q32: Proper lighting
    setSelectValue("64-192", NEUTRAL); // Q33: Audio visuals availability

    // --- 9. COURSE OUTLINE (Questions 34-36) ---
    console.log("\n📋 Filling COURSE OUTLINE...");
    setRadioValue("65-193", "5");             // Q34: Lecturer provides course outline → True
    setRadioValue("65-194", QUESTION_35_VALUE); // Q35: Bought handout → False
    setTextareaValue("65-195", "");            // Q36: If YES, how much? → Empty (since Q35 is False)

    // --- 10. GENERAL COMMENT (Question 37) ---
    console.log("\n📋 Filling GENERAL COMMENT...");
    setTextareaValue("66-196", GENERAL_COMMENT); // Q37: General comment

    console.log("\n✅ Survey auto-fill complete!");
    console.log("📌 Remember to manually select your gender if not set.");
    console.log("📌 Review all answers before submitting.");

})();
