// SPDX-FileCopyrightText: 2023 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
//
// SPDX-License-Identifier: BSD-2-Clause

"use strict";

let questionData = [
  {
    "is_sequence": true,
    "connection": "Adjectives that apply to Kitteh",
    "clues": ["thirsty_", "Cuddly_", "disaster_", "two_distinct_"]
  }
];

function goToRound(data, round) {
  fetch(data).then(r => r.json()).then( r => {
    questionData = r;
    document.getElementById("round-info").textContent = (round || "Round data: " + data);
    [...document.querySelectorAll("#selection span")].forEach(
        (e, i) => e.classList.toggle("available", i < questionData.length)
    );
    questionSelect();
  });
}

function questionSelect()
{
  document.body.classList.remove("state-question");
  document.body.classList.add("state-selection");
}

function selectQuestion(e, questionIndex)
{
  console.log(e, questionIndex);
  if (!e.target.classList.contains("available")) {
    return;
  }
  if (!e.target.classList.contains("selected")) {
    e.target.classList.add("selected");
    window.setTimeout(() => selectQuestion(e, questionIndex), 500);
    return;
  }

  e.target.classList.remove("available");
  e.target.classList.remove("selected");

  const data = questionData[questionIndex];
  const questionBlock = document.getElementById("question");
  const clues = [...questionBlock.querySelectorAll("span")]

  questionBlock.classList.remove("answered");

  clues.forEach((e, i) => {
    e.classList.remove("active");
    e.classList.remove("revealed");
    e.textContent = data.clues[i];
  });

  clues[0].classList.add("active")
  if (data.is_sequence) {
    clues[3].setAttribute("data-answer", clues[3].textContent);
    clues[3].textContent = "?";
    clues[3].classList.add("revealed");
  }

  const connection = questionBlock.querySelector(".connection");
  connection.textContent = data.connection;

  document.body.classList.remove("state-selection");
  document.body.classList.add("state-question");
}

function nextClue()
{
  const current = document.querySelector(".active");
  const next = current.nextElementSibling;

  if (!next || next.classList.contains("revealed")) {
    return;
  }

  next.classList.add("active");
  current.classList.remove("active");
}

function revealAnswer() {
  const questionBlock = document.getElementById("question");

  questionBlock.classList.add("answered");
  questionBlock.querySelectorAll("[data-answer]").forEach(e => e.textContent = e.getAttribute("data-answer"));
}

[...document.querySelectorAll("#selection span")].forEach(
  (e, i) => e.addEventListener("click", e => selectQuestion(e, i))
);
goToRound("connections.json", "Round 1: Connections");
