
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#define MAX_TASKS 100
#define TITLE_SIZE 100

typedef struct {
    int id;
    char title[TITLE_SIZE];
    int priority;
    int daysLeft;
    int completed;
} Task;

Task tasks[MAX_TASKS];
int taskCount = 0;
int nextId = 1;

/* Safely read an integer */
int readInt(const char *message) {
    char input[100];
    int value;
    char *end;

    while (1) {
        printf("%s", message);

        if (fgets(input, sizeof(input), stdin) == NULL) {
            printf("Input error.\n");
            exit(1);
        }

        value = (int)strtol(input, &end, 10);

        while (*end == ' ' || *end == '\t')
            end++;

        if (end != input && (*end == '\n' || *end == '\0'))
            return value;

        printf("Please enter a valid integer.\n");
    }
}

/* Read a task title */
void readTitle(char title[]) {
    printf("Enter task title: ");
    if (fgets(title, TITLE_SIZE, stdin) == NULL) {
        title[0] = '\0';
        return;
    }

    title[strcspn(title, "\n")] = '\0';

    if (strlen(title) == 0)
        strcpy(title, "Untitled Task");
}

/* Add a new task */
void addTask(void) {
    if (taskCount >= MAX_TASKS) {
        printf("Task limit reached!\n");
        return;
    }

    Task t;
    t.id = nextId++;

    readTitle(t.title);

    do {
        t.priority = readInt("Enter priority (1-5, 5 highest): ");
        if (t.priority < 1 || t.priority > 5)
            printf("Priority must be between 1 and 5.\n");
    } while (t.priority < 1 || t.priority > 5);

    t.daysLeft = readInt(
        "Days until deadline (negative = overdue, 0 = today): ");

    t.completed = 0;
    tasks[taskCount++] = t;

    printf("Task added successfully! ID: %d\n", t.id);
}

/* Display all tasks */
void displayTasks(void) {
    if (taskCount == 0) {
        printf("No tasks available.\n");
        return;
    }

    printf("\n%-5s %-25s %-10s %-12s %-12s\n",
           "ID", "Title", "Priority", "Days Left", "Status");
    printf("-------------------------------------------------------------------\n");

    for (int i = 0; i < taskCount; i++) {
        printf("%-5d %-25.25s %-10d %-12d %-12s\n",
               tasks[i].id,
               tasks[i].title,
               tasks[i].priority,
               tasks[i].daysLeft,
               tasks[i].completed ? "Completed" : "Pending");
    }
}

/* Find a task by ID */
int findTaskIndex(int id) {
    for (int i = 0; i < taskCount; i++) {
        if (tasks[i].id == id)
            return i;
    }
    return -1;
}

void searchTask(void) {
    int id = readInt("Enter task ID to search: ");
    int index = findTaskIndex(id);

    if (index == -1) {
        printf("Task not found.\n");
        return;
    }

    Task t = tasks[index];

    printf("\nTask found!\n");
    printf("ID: %d\nTitle: %s\nPriority: %d\n",
           t.id, t.title, t.priority);
    printf("Days until deadline: %d\n",
           t.daysLeft);
    printf("Status: %s\n",
           t.completed ? "Completed" : "Pending");
}

/* Mark a task as completed */
void completeTask(void) {
    int id = readInt("Enter task ID to complete: ");
    int index = findTaskIndex(id);

    if (index == -1) {
        printf("Task not found.\n");
        return;
    }

    if (tasks[index].completed) {
        printf("Task is already completed.\n");
        return;
    }

    tasks[index].completed = 1;
    printf("Task marked as completed!\n");
}

/*
   Higher priority comes first.
   For equal priorities, earlier deadlines come first.
   If both are equal, lower ID comes first.
*/
int comesBefore(Task a, Task b) {
    if (a.priority != b.priority)
        return a.priority > b.priority;

    if (a.daysLeft != b.daysLeft)
        return a.daysLeft < b.daysLeft;

    return a.id < b.id;
}

/* Insertion sort: highest-priority tasks first */
void sortTasks(void) {
    for (int i = 1; i < taskCount; i++) {
        Task key = tasks[i];
        int j = i - 1;

        while (j >= 0 && comesBefore(key, tasks[j])) {
            tasks[j + 1] = tasks[j];
            j--;
        }

        tasks[j + 1] = key;
    }

    printf("Tasks sorted by priority and deadline.\n");
    displayTasks();
}

/* ---------- Binary Max-Heap ---------- */

Task heap[MAX_TASKS];
int heapSize = 0;

/* Move a newly inserted task upward */
void heapifyUp(int index) {
    while (index > 0) {
        int parent = (index - 1) / 2;

        if (comesBefore(heap[parent], heap[index]))
            break;

        Task temp = heap[parent];
        heap[parent] = heap[index];
        heap[index] = temp;

        index = parent;
    }
}

/* Insert a task into the priority queue */
void heapInsert(Task t) {
    if (heapSize >= MAX_TASKS)
        return;

    heap[heapSize] = t;
    heapifyUp(heapSize);
    heapSize++;
}

/* Restore heap order after removing the root */
void heapifyDown(int index) {
    while (1) {
        int best = index;
        int left = 2 * index + 1;
        int right = 2 * index + 2;

        if (left < heapSize &&
            comesBefore(heap[left], heap[best]))
            best = left;

        if (right < heapSize &&
            comesBefore(heap[right], heap[best]))
            best = right;

        if (best == index)
            break;

        Task temp = heap[index];
        heap[index] = heap[best];
        heap[best] = temp;

        index = best;
    }
}

/* Remove and return the highest-priority task */
Task extractMax(void) {
    Task result = heap[0];

    heapSize--;
    if (heapSize > 0) {
        heap[0] = heap[heapSize];
        heapifyDown(0);
    }

    return result;
}

/* Generate the recommended schedule */
void scheduleTasks(void) {
    heapSize = 0;

    for (int i = 0; i < taskCount; i++) {
        if (!tasks[i].completed)
            heapInsert(tasks[i]);
    }

    if (heapSize == 0) {
        printf("No pending tasks to schedule.\n");
        return;
    }

    printf("\n===== RECOMMENDED TASK SCHEDULE =====\n");

    int position = 1;

    while (heapSize > 0) {
        Task t = extractMax();

        printf("%d. [ID: %d] %s | Priority: %d | ",
               position++, t.id, t.title, t.priority);

        if (t.daysLeft < 0)
            printf("OVERDUE by %d day(s)\n", -t.daysLeft);
        else if (t.daysLeft == 0)
            printf("Deadline: TODAY\n");
        else
            printf("Deadline in %d day(s)\n", t.daysLeft);
    }

    printf("\nScheduling complete. Tasks were not marked completed.\n");
}

/* Main menu */
int main(void) {
    int choice;

    do {
        printf("\n====================================\n");
        printf("     SMART TASK SCHEDULER IN C\n");
        printf("====================================\n");
        printf("1. Add Task\n");
        printf("2. Display All Tasks\n");
        printf("3. Search Task by ID\n");
        printf("4. Sort Tasks by Priority\n");
        printf("5. Generate Recommended Schedule\n");
        printf("6. Mark Task as Completed\n");
        printf("7. Exit\n");

        choice = readInt("Enter your choice: ");

        switch (choice) {
            case 1:
                addTask();
                break;
            case 2:
                displayTasks();
                break;
            case 3:
                searchTask();
                break;
            case 4:
                sortTasks();
                break;
            case 5:
                scheduleTasks();
                break;
            case 6:
                completeTask();
                break;
            case 7:
                printf("Thank you for using Smart Task Scheduler!\n");
                break;
            default:
                printf("Invalid choice. Please select 1-7.\n");
        }
    } while (choice != 7);

    return 0;
}
