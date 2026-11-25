from __future__ import annotations

from typing import Dict, List

DEMO_COURSE_TITLE = "CS-302: Operating Systems (B.Tech Engineering)"

DEMO_SYLLABUS_TEXT = """
CS-302: OPERATING SYSTEMS — PRESCRIBED UNIVERSITY SYLLABUS
Credits: 4 | Exam Duration: 3 Hours | Total Marks: 100

UNIT 1: Process Management & CPU Scheduling
- Process Concept, Process Control Block (PCB), Process States (New, Ready, Running, Waiting, Terminated) and Context Switching overhead.
- CPU Scheduling Criteria: CPU Utilization, Throughput, Turnaround Time (TAT = Completion Time - Arrival Time), Waiting Time (WT = TAT - Burst Time), Response Time.
- Preemptive vs Non-Preemptive Scheduling Algorithms: First-Come First-Served (FCFS) and Convoy Effect, Shortest Job First (SJF), Shortest Remaining Time First (SRTF), Priority Scheduling (Aging to prevent Starvation), Round Robin (RR) with Time Quantum q, Multilevel Queue and Multilevel Feedback Queue Scheduling.

UNIT 2: Process Synchronization & Deadlocks
- Race Conditions, Critical Section Problem Requirements (Mutual Exclusion, Progress, Bounded Waiting), Peterson's Solution, Hardware Synchronization (TestAndSet, CompareAndSwap).
- Semaphores (Counting & Binary), Mutex Locks, Classic Synchronization Problems (Bounded Buffer / Producer-Consumer, Readers-Writers, Dining Philosophers).
- Deadlock Characterization (4 Coffman Conditions: Mutual Exclusion, Hold and Wait, No Preemption, Circular Wait), Resource Allocation Graphs (RAG).
- Deadlock Handling: Prevention, Avoidance using Banker's Algorithm (Need = Max - Allocation, Safety Algorithm, Resource-Request Algorithm), Deadlock Detection and Recovery.

UNIT 3: Memory Management & Paging
- Logical vs Physical Address Space, Memory Management Unit (MMU), Dynamic Relocation, Swapping.
- Contiguous Memory Allocation: Fixed & Variable Partitioning, Allocation Strategies (First Fit, Best Fit, Worst Fit), Internal vs External Fragmentation, Compaction.
- Paging Hardware: Page Number (p) and Page Offset (d), Page Table, Translation Lookaside Buffer (TLB), Hit Ratio (h), Effective Memory Access Time: EMAT = h*(t_TLB + t_mem) + (1 - h)*(t_TLB + 2*t_mem).
- Multi-level Paging, Inverted Page Tables, Segmentation and Paged Segmentation.

UNIT 4: Virtual Memory & Disk Scheduling
- Virtual Memory Concepts, Demand Paging, Valid-Invalid Bit, Page Fault Handling Routine, Effective Access Time with Page Fault Rate p: EAT = (1 - p)*ma + p*(Page Fault Service Time).
- Page Replacement Algorithms: FIFO (and Belady's Anomaly), Optimal Page Replacement (OPT), Least Recently Used (LRU), Second-Chance / Clock Algorithm.
- Allocation of Frames, Thrashing and Working Set Model (Delta window).
- Secondary Storage & Disk Scheduling Algorithms: Seek Time, Rotational Latency, Transfer Time, FCFS, Shortest Seek Time First (SSTF), SCAN (Elevator), C-SCAN, LOOK and C-LOOK.
""".strip()


DEMO_PYQ_PAPERS: List[Dict[str, str]] = [
    {
        "filename": "OS_PYQ_2025_EndSem.pdf",
        "text": """
[End-Semester Examination 2025 | CS-302 Operating Systems]
Q1 (10 Marks) [CPU Scheduling Algorithms]:
Consider the following set of processes with arrival times and CPU burst times (in ms):
P1 (AT=0, BT=8), P2 (AT=1, BT=4), P3 (AT=2, BT=9), P4 (AT=3, BT=5).
Draw the Gantt chart and calculate the Average Waiting Time and Average Turnaround Time using:
(a) Preemptive SJF (SRTF)
(b) Round Robin with time quantum q = 3 ms.
Explain why FCFS suffers from the Convoy Effect.

Q2 (10 Marks) [Banker's Algorithm for Deadlock Avoidance]:
A system has 5 processes (P0 to P4) and 3 resource types A (10 instances), B (5 instances), C (7 instances).
At T0, Allocation and Max matrices are given:
P0: Alloc(0,1,0) Max(7,5,3); P1: Alloc(2,0,0) Max(3,2,2); P2: Alloc(3,0,2) Max(9,0,2); P3: Alloc(2,1,1) Max(2,2,2); P4: Alloc(0,0,2) Max(4,3,3).
Calculate the Need matrix, Available vector, and determine if the system is in a safe state using Banker's Algorithm. If P1 requests (1,0,2), can it be granted immediately?

Q3 (8 Marks) [TLB & Effective Memory Access Time]:
A paging system uses a TLB with access time 15 ns and main memory access time 120 ns. If the TLB hit ratio is 90%, calculate the Effective Memory Access Time (EMAT). Also compute page table size for a 32-bit logical address space, 4 KB page size, and 4-byte page table entry.

Q4 (8 Marks) [Page Replacement Algorithms]:
Given the page reference string: 7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2 with 3 frames.
Calculate the total number of page faults under FIFO, Optimal (OPT), and LRU page replacement algorithms.
""",
    },
    {
        "filename": "OS_PYQ_2024_EndSem.pdf",
        "text": """
[End-Semester Examination 2024 | CS-302 Operating Systems]
Q1 (10 Marks) [Banker's Algorithm & Deadlock Characterization]:
State and explain the four Coffman conditions necessary for a deadlock to occur. How does Deadlock Prevention break Circular Wait and Hold-and-Wait?
Also solve: Given Available = (3, 3, 2) and Need matrix for P0..P4, verify whether a safe sequence exists using Banker's Safety Algorithm.

Q2 (10 Marks) [CPU Scheduling Algorithms]:
Compare Preemptive Priority Scheduling and Round Robin (RR) scheduling with respect to Starvation, Aging, Response Time, and Context Switch Overhead.
Compute Average Waiting Time for processes P1(0, 10), P2(1, 5), P3(2, 2) under SRTF and RR (q=2).

Q3 (8 Marks) [Paging & TLB]:
Explain the hardware support required for Paging with TLB. If a memory access takes 100 ns and TLB lookup takes 20 ns, what hit ratio is needed to achieve an Effective Memory Access Time (EMAT) of at most 125 ns?

Q4 (8 Marks) [Demand Paging & Page Replacement]:
What is Belady's Anomaly? Demonstrate with the reference string 1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5 for 3 frames vs 4 frames using FIFO. Explain Thrashing and the Working Set model.
""",
    },
    {
        "filename": "OS_PYQ_2023_EndSem.pdf",
        "text": """
[End-Semester Examination 2023 | CS-302 Operating Systems]
Q1 (10 Marks) [CPU Scheduling & Convoy Effect]:
Calculate Turnaround Time and Waiting Time for FCFS, Non-Preemptive SJF, and Round Robin (q=4) for 4 processes. Define Response Time and Throughput. Why does small time quantum degrade Round Robin performance?

Q2 (8 Marks) [Deadlock Characterization & Banker's Algorithm]:
Differentiate between Deadlock Prevention, Deadlock Avoidance, and Deadlock Detection. Draw a Resource Allocation Graph (RAG) showing a cycle that is NOT a deadlock when resources have multiple instances.

Q3 (8 Marks) [Contiguous Memory Allocation & Fragmentation]:
Given memory partitions of 100 KB, 500 KB, 200 KB, 300 KB, and 600 KB (in order), place processes of 212 KB, 417 KB, 112 KB, and 426 KB using First Fit, Best Fit, and Worst Fit. Distinguish Internal vs External Fragmentation.

Q4 (10 Marks) [Page Replacement & Effective Access Time]:
A memory access takes 200 ns, and servicing a page fault takes 8 milliseconds. If the page fault rate is p = 0.0001 (1 in 10,000), calculate the Effective Access Time (EAT). Compare LRU vs Optimal page replacement on 1, 2, 3, 4, 2, 1, 5, 6, 2, 1, 2, 3, 7, 6, 3, 2, 1, 2, 3, 6 with 4 frames.
""",
    },
    {
        "filename": "OS_PYQ_2022_EndSem.pdf",
        "text": """
[End-Semester Examination 2022 | CS-302 Operating Systems]
Q1 (8 Marks) [Process Synchronization & Semaphores]:
What is a Race Condition? List the three requirements of a valid Critical Section solution (Mutual Exclusion, Progress, Bounded Waiting). Write pseudocode for the Bounded Buffer (Producer-Consumer) problem using counting semaphores `empty`, `full`, and binary semaphore `mutex`.

Q2 (10 Marks) [Banker's Algorithm & Deadlocks]:
Explain the Safety Algorithm and Resource-Request Algorithm in Banker's Algorithm. Why must Need[i] <= Available be checked before tentatively allocating resources?

Q3 (8 Marks) [Paging & TLB]:
Explain how logical address (p, d) is translated to physical address (f, d) in Paging. Given TLB hit ratio = 85%, TLB search time = 10 ns, main memory access = 100 ns, calculate EMAT.

Q4 (8 Marks) [Disk Scheduling Algorithms]:
A disk drive has 200 cylinders (0 to 199). The head is currently at cylinder 53, moving towards 199. Request queue: 98, 183, 37, 122, 14, 124, 65, 67. Calculate total head movement under SSTF, SCAN, and C-SCAN.
""",
    },
]
