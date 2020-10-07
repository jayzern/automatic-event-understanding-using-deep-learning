import ast


with open('/media/data-disk/data/event-rep/exp9_0.1-16-16-Roles2Args3Mods-NoFrAn-v1/NN_train', "r") as f:
    for count, line in enumerate(f):
        d = eval(line)

        if len(d) < 7:
            print(d)
            print(count)
            break

        # if count == 123:
        #     print(d)
        #     break

        # try:
        #     temp = ast.literal_eval(line)
        # except:
        #     print(line)
        #     break

# print("hello word")